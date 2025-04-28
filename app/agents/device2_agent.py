import os
import logging
from pyats.topology import loader
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_core.tools import tool
from dotenv import load_dotenv
from langchain_core.tools import tool, render_text_description

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_linux_command(command: str, device_name: str):
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

@tool("run_command_tool")
def run_command_tool(input_text: str) -> dict:
    """
    Execute a command on a specified device.
    Input format: "<device_name>: <command>"
    Example: "device1: ifconfig -a"
    """
    try:
        # Split input into device name and command
        device_name, command = input_text.split(":", 1)
        device_name = device_name.strip()
        command = command.strip()
        
        return run_linux_command(command, device_name)
    except ValueError:
        return {"status": "error", "error": "Invalid input format. Use '<device_name>: <command>'."}

# Define the LLM model
llm = ChatOpenAI(model_name="gpt-4o", temperature=0.1)

# Create tool list
tools = [run_command_tool]

# Create tool descriptions
tool_descriptions = render_text_description(tools)# Define the prompt template
template = '''
You are an Infrastructure Agent that can interact with Linux systems.

You can execute commands on devices to gather information, configure settings, and perform system operations.

**INSTRUCTIONS:**
- Use the run_command_tool to execute commands on the specified device
- Always check command outputs to ensure operations completed successfully
- Provide clear explanations of command results

**TOOLS:**
{tools}

**Available Tool Names (use exactly as written):**  
{tool_names}

To use a tool, follow this format:

Thought: Do I need to use a tool? Yes
Action: run_command_tool
Action Input: "<device_name>: <command>"
Observation: [Result of the command]
Final Answer: [Your response to the user]

Begin!

{chat_history}

New input: {input}

{agent_scratchpad}
'''

# Create the agent
input_variables = ["input", "agent_scratchpad", "chat_history"]
prompt_template = PromptTemplate(
    template=template,
    input_variables=input_variables,
    partial_variables={
        "tools": tool_descriptions,
        "tool_names": ", ".join([t.name for t in tools])
    }
)

agent = create_react_agent(llm, tools, prompt_template)

# Initialize the agent executor
agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    handle_parsing_errors=True, 
    verbose=True
)

def handle_command(command: str, device_name: str):
    try:
        logging.info(f"Executing command on {device_name}: {command}")
        response = agent_executor.invoke(f"{device_name}: {command.strip()}")
        return response
    except Exception as e:
        logging.error(f"Error executing command on {device_name}: {str(e)}")
        return {"status": "error", "error": str(e)}