import os
import logging
from typing import TypedDict, List, Dict, Any, Literal, Union, Annotated
import streamlit as st
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# Import LangGraph components
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor, ToolInvocation

# Import our agent modules
from agents.device1_agent import invoke as device1_invoke
from agents.device2_agent import invoke as device2_invoke
from agents.netbox_agent import invoke as netbox_invoke

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the state for our orchestrator agent
class OrchestratorState(TypedDict):
    messages: List[Dict[str, Any]]
    next: Literal["assistant", "action", "end"]

# Define sub-agent tools
def device1_agent_func(input_text: str) -> dict:
    """Query or execute commands on device1"""
    return device1_invoke(input_text)

def device2_agent_func(input_text: str) -> dict:
    """Query or execute commands on device2"""
    return device2_invoke(input_text)

def netbox_agent_func(input_text: str) -> dict:
    """Query or modify NetBox infrastructure data"""
    return netbox_invoke(input_text)

# Define tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "device1_agent",
            "description": "Use for commands on Device1 (Linux host). This agent executes Linux commands on device1.",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_text": {
                        "type": "string",
                        "description": "Command or query for device1"
                    }
                },
                "required": ["input_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "device2_agent",
            "description": "Use for commands on Device2 (Linux host). This agent executes Linux commands on device2.",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_text": {
                        "type": "string",
                        "description": "Command or query for device2"
                    }
                },
                "required": ["input_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "netbox_agent",
            "description": "Use for NetBox operations and queries. This agent interacts with the NetBox API for infrastructure documentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_text": {
                        "type": "string",
                        "description": "Query or operation for NetBox"
                    }
                },
                "required": ["input_text"]
            }
        }
    }
]

# Initialize the LLM
llm = ChatOpenAI(model_name="gpt-4o", temperature=0.1)

# Create the system prompt
system_prompt = """You are an Infrastructure Agent that helps manage network infrastructure.

You have access to multiple tools:
1. device1_agent: Execute commands on Device1 (Linux host)
2. device2_agent: Execute commands on Device2 (Linux host)
3. netbox_agent: Query or modify NetBox infrastructure data

INSTRUCTIONS:
- Analyze the user's request to determine which agent(s) to use
- Use device agents for Linux operations (e.g., networking, processes)
- Use the NetBox agent for infrastructure documentation
- You can use multiple agents to fulfill complex requests
- Provide clear explanations of your findings

Examples:
- To check device1 network: Use device1_agent
- To compare both devices: Use both device1_agent and device2_agent
- To query infrastructure data: Use netbox_agent
"""

# Create a tool executor
tool_executor = ToolExecutor({
    "device1_agent": device1_agent_func,
    "device2_agent": device2_agent_func,
    "netbox_agent": netbox_agent_func
})

# Create the orchestrator graph
def create_orchestrator():
    # Create the LLM node
    def call_llm(state):
        messages = state["messages"]
        response = llm.invoke([
            ("system", system_prompt),
            *messages,
        ])
        
        tool_call = response.tool_calls
        if tool_call:
            return {"messages": messages + [{"role": "assistant", "content": response.content, "tool_calls": tool_call}], "next": "action"}
        else:
            return {"messages": messages + [{"role": "assistant", "content": response.content}], "next": "end"}
    
    # Create the tool node
    def call_tool(state):
        messages = state["messages"]
        last_message = messages[-1]
        
        if "tool_calls" not in last_message:
            return {"messages": messages, "next": "end"}
        
        tool_calls = last_message["tool_calls"]
        
        if not tool_calls:
            return {"messages": messages, "next": "end"}
        
        all_results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            action = ToolInvocation(
                tool=tool_name,
                tool_input=tool_args.get("input_text", "")
            )
            
            # Execute the tool
            result = tool_executor.invoke(action)
            tool_result = f"Result: {result}"
            all_results.append({"tool_call_id": tool_call["id"], "role": "tool", "name": tool_call["name"], "content": tool_result})
        
        messages = messages + all_results
        return {"messages": messages, "next": "assistant"}
    
    # Define the graph
    workflow = StateGraph(OrchestratorState)
    
    # Add nodes
    workflow.add_node("assistant", call_llm)
    workflow.add_node("action", call_tool)
    
    # Add edges
    workflow.add_edge("assistant", "action")
    workflow.add_edge("action", "assistant")
    workflow.add_edge("assistant", END)
    workflow.add_edge("action", END)
    
    # Set the entry point
    workflow.set_entry_point("assistant")
    
    # Compile the graph
    return workflow.compile()

# Create the orchestrator agent
orchestrator = create_orchestrator()

# Streamlit UI
def main():
    st.title("Infrastructure Agent")

    # Create a chat interface
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.orchestrator_state = {
            "messages": [],
            "next": "assistant"
        }

    # Display previous messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Get user input
    if prompt := st.chat_input("Ask a question about your infrastructure..."):
        # Display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Update the orchestrator state with the new message
        st.session_state.orchestrator_state["messages"].append({"role": "human", "content": prompt})
        
        # Get response from the agent
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Run the graph
                result = orchestrator.invoke(st.session_state.orchestrator_state)
                
                # Update the state for the next interaction
                st.session_state.orchestrator_state = result
                
                # Extract the final assistant message
                assistant_messages = [msg for msg in result["messages"] if msg["role"] == "assistant"]
                
                if assistant_messages:
                    response_text = assistant_messages[-1]["content"]
                else:
                    response_text = "No response generated from the agent."
                
                st.markdown(response_text)
        
        # Store assistant response in the UI messages
        st.session_state.messages.append({"role": "assistant", "content": response_text})

if __name__ == "__main__":
    main()