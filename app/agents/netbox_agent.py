import os
import logging
import requests
from typing import TypedDict, List, Dict, Any, Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from dotenv import load_dotenv

# Import LangGraph components
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor, ToolInvocation

# Load environment variables
load_dotenv()
NETBOX_URL = os.getenv("NETBOX_BASE_URL", "http://netbox:8080").rstrip('/')
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the state for our agent
class NetBoxAgentState(TypedDict):
    messages: List[Dict[str, Any]]
    next: Literal["assistant", "action", "end"]

class NetBoxController:
    def __init__(self, netbox_url, api_token):
        self.netbox = netbox_url
        self.api_token = api_token
        self.headers = {
            'Accept': 'application/json',
            'Authorization': f"Token {self.api_token}",
        }

    def get_api(self, api_url: str, params: dict = None):
        """Perform a GET request to NetBox API."""
        full_url = f"{self.netbox}/{api_url.lstrip('/')}"
        logging.info(f"GET Request to URL: {full_url}")
        
        try:
            response = requests.get(full_url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"GET request failed: {e}")
            return {"error": f"Request failed: {e}"}

    def post_api(self, api_url: str, payload: dict):
        """Perform a POST request to NetBox API."""
        full_url = f"{self.netbox}/{api_url.lstrip('/')}"
        logging.info(f"POST Request to URL: {full_url}")
        
        try:
            response = requests.post(full_url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"POST request failed: {e}")
            return {"error": f"Request failed: {e}"}

# Define tool functions
def get_netbox_data(api_url: str):
    """Get data from NetBox API."""
    # Ensure the URL doesn't start with the full base URL
    if api_url.startswith(NETBOX_URL):
        api_url = api_url.replace(NETBOX_URL, "")
    
    # Make sure it starts with /api/
    if not api_url.startswith("/api/"):
        api_url = f"/api/{api_url.lstrip('/')}"
    
    netbox_controller = NetBoxController(NETBOX_URL, NETBOX_TOKEN)
    return netbox_controller.get_api(api_url)

def create_netbox_data(api_url: str, payload: dict):
    """Create data in NetBox API."""
    # Ensure the URL doesn't start with the full base URL
    if api_url.startswith(NETBOX_URL):
        api_url = api_url.replace(NETBOX_URL, "")
    
    # Make sure it starts with /api/
    if not api_url.startswith("/api/"):
        api_url = f"/api/{api_url.lstrip('/')}"
    
    netbox_controller = NetBoxController(NETBOX_URL, NETBOX_TOKEN)
    return netbox_controller.post_api(api_url, payload)

# Define tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_netbox_data_tool",
            "description": "Fetch data from NetBox using the API URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "api_url": {
                        "type": "string",
                        "description": "The API URL path, e.g., '/api/dcim/devices/'"
                    }
                },
                "required": ["api_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_netbox_data_tool",
            "description": "Create new data in NetBox using the API URL and payload.",
            "parameters": {
                "type": "object",
                "properties": {
                    "api_url": {
                        "type": "string",
                        "description": "The API URL path, e.g., '/api/dcim/devices/'"
                    },
                    "payload": {
                        "type": "object",
                        "description": "The data to be created"
                    }
                },
                "required": ["api_url", "payload"]
            }
        }
    }
]

# Initialize the LLM
llm = ChatOpenAI(model_name="gpt-4o", temperature=0.1)

# Create the system prompt
system_prompt = """You are a NetBox specialist that helps manage network infrastructure data.

**IMPORTANT: URL FORMAT RULES**
- Always use the format `/api/dcim/devices/` (not the full URL)
- Never include the base URL ("http://netbox:8080") in your requests
- Example: To get device1, use `/api/dcim/devices/?name=device1`

You have two tools available:
1. get_netbox_data_tool: Use this to fetch data from NetBox
2. create_netbox_data_tool: Use this to create new data in NetBox

When using these tools, follow these guidelines:
- Always check the response to ensure the operation was successful
- For GET requests, specify filters in the URL query string
- For POST requests, provide a complete and valid payload
"""

# Create a tool executor
tool_executor = ToolExecutor({
    "get_netbox_data_tool": get_netbox_data,
    "create_netbox_data_tool": create_netbox_data
})

# Create the state graph
def create_netbox_agent():
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
            
            # Map the tool name to the function
            if tool_name == "get_netbox_data_tool":
                action = ToolInvocation(
                    tool=tool_name,
                    tool_input=tool_args.get("api_url", "")
                )
            elif tool_name == "create_netbox_data_tool":
                action = ToolInvocation(
                    tool=tool_name,
                    tool_input={
                        "api_url": tool_args.get("api_url", ""),
                        "payload": tool_args.get("payload", {})
                    }
                )
            else:
                continue
            
            # Execute the tool
            result = tool_executor.invoke(action)
            tool_result = f"Result: {result}"
            all_results.append({"tool_call_id": tool_call["id"], "role": "tool", "name": tool_call["name"], "content": tool_result})
        
        messages = messages + all_results
        return {"messages": messages, "next": "assistant"}
    
    # Define the graph
    workflow = StateGraph(NetBoxAgentState)
    
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

# Create the netbox agent
netbox_agent = create_netbox_agent()

# Function for the main.py to use
def invoke(input_text):
    """
    Process a query to NetBox
    """
    # Initialize the state
    state = {
        "messages": [{"role": "human", "content": input_text}],
        "next": "assistant"
    }
    
    # Run the graph
    result = netbox_agent.invoke(state)
    
    # Extract the final assistant message
    assistant_messages = [msg for msg in result["messages"] if msg["role"] == "assistant"]
    
    if assistant_messages:
        final_message = assistant_messages[-1]["content"]
    else:
        final_message = "No response generated from the agent."
    
    return {"output": final_message}