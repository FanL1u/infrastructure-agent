import os
import logging
from typing import TypedDict, List, Dict, Any, Annotated, Literal
from pyats.topology import loader
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from dotenv import load_dotenv

# Import LangGraph components
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor, tools_to_graph

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the state for our agent
class DeviceAgentState(TypedDict):
    messages: List[Dict[str, Any]]
    next: Literal["assistant", "action", "end"]

# Function to execute Linux commands
def run_linux_command(command: str, device_name: str = "device2"):
    """Execute a Linux command on a specified device."""
    try:
        # Load testbed and target device
        testbed = loader.load('../testbed.yaml')
        
        if device_name not in testbed.devices:
            return {"status": "error", "error": f"Device '{device_name}' not found in testbed."}
        
        device = testbed.devices[device_name]
        
        # Connect to device if not already connected
        if not device.is_connected():
            logger.info(f"Connecting to {device_name}...")
            device.connect()
        
        # Execute the command
        logger.info(f"Running command on {device_name}: {command}")
        output = device.execute(command)
        
        # Disconnect
        device.disconnect()
        
        return {"status": "completed", "device": device_name, "output": output}
    
    except Exception as e:
        logger.error(f"Error executing command on {device_name}: {str(e)}")
        return {"status": "error", "error": str(e)}

# Define tools
from langgraph.prebuilt import ToolInvocation

# Define tool for running commands
def run_command_tool(input_text: str) -> dict:
    """
    Execute a command on a specified device.
    Input format: "<device_name>: <command>" or just "<command>" (defaults to device2)
    Example: "device2: ifconfig -a" or "ifconfig -a"
    """
    try:
        # Check if device name is specified
        if ":" in input_text:
            device_name, command = input_text.split(":", 1)
            device_name = device_name.strip()
            command = command.strip()
        else:
            device_name = "device2"
            command = input_text.strip()
        
        return run_linux_command(command, device_name)
    except ValueError:
        return {"status": "error", "error": "Invalid input format. Use '<device_name>: <command>' or just '<command>'."}

tools = [
    {
        "type": "function",
        "function": {
            "name": "run_command_tool",
            "description": "Execute a command on device2. If device name is not specified, defaults to device2.",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_text": {
                        "type": "string",
                        "description": "The command to execute. Format: '<device_name>: <command>' or just '<command>'."
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
system_prompt = """You are an Infrastructure Agent that can interact with Linux systems.

You can execute commands on devices to gather information, configure settings, and perform system operations.

INSTRUCTIONS:
- Use the run_command_tool to execute commands on the device
- Always check command outputs to ensure operations completed successfully
- Provide clear explanations of command results
- Your default device is device2 if not specified

Examples:
To check network interfaces: Use run_command_tool with "ifconfig -a"
To check running processes: Use run_command_tool with "ps aux"
"""

# Create the prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="messages"),
    ("human", "{input}")
])

# Create the state graph
def create_device_agent():
    # Create a tool executor
    tool_executor = ToolExecutor({"run_command_tool": run_command_tool})
    
    # Create the LLM node
    def call_llm(state):
        messages = state["messages"]
        response = llm.invoke([
            ("system", system_prompt),
            *messages,
        ])
        
        if not any(tool["function"]["name"] == "run_command_tool" for tool in tools if "function" in tool):
            return {"messages": messages + [{"role": "assistant", "content": response.content}], "next": "end"}
        
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
            action = ToolInvocation(
                tool=tool_call["name"],
                tool_input=tool_call["args"].get("input_text", "")
            )
            
            # Execute the tool
            result = tool_executor.invoke(action)
            tool_result = f"Result: {result}"
            all_results.append({"tool_call_id": tool_call["id"], "role": "tool", "name": tool_call["name"], "content": tool_result})
        
        messages = messages + all_results
        return {"messages": messages, "next": "assistant"}
    
    # Define the graph
    workflow = StateGraph(DeviceAgentState)
    
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

# Create the device agent
device_agent = create_device_agent()

# Function for the main.py to use
def invoke(input_text):
    """
    Process a command for device2
    """
    # Initialize the state
    state = {
        "messages": [{"role": "human", "content": input_text}],
        "next": "assistant"
    }
    
    # Run the graph
    result = device_agent.invoke(state)
    
    # Extract the final assistant message
    assistant_messages = [msg for msg in result["messages"] if msg["role"] == "assistant"]
    
    if assistant_messages:
        final_message = assistant_messages[-1]["content"]
    else:
        final_message = "No response generated from the agent."
    
    return {"output": final_message}