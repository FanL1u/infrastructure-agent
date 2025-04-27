import os
import logging
import requests
from langchain.tools import Tool
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
NETBOX_URL = os.getenv("NETBOX_BASE_URL").rstrip('/')
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)

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

def get_netbox_data(api_url: str):
    """Get data from NetBox API."""
    netbox_controller = NetBoxController(NETBOX_URL, NETBOX_TOKEN)
    return netbox_controller.get_api(api_url)

def create_netbox_data(api_url: str, payload: dict):
    """Create data in NetBox API."""
    netbox_controller = NetBoxController(NETBOX_URL, NETBOX_TOKEN)
    return netbox_controller.post_api(api_url, payload)

# Define tools
get_netbox_data_tool = Tool(
    name="get_netbox_data_tool",
    func=get_netbox_data,
    description="Fetch data from NetBox using the API URL."
)

create_netbox_data_tool = Tool(
    name="create_netbox_data_tool",
    func=create_netbox_data,
    description="Create new data in NetBox using the API URL and payload."
)

# Define the tools
tools = [get_netbox_data_tool, create_netbox_data_tool]

# Initialize the LLM
llm = ChatOpenAI(model_name="gpt-4o", temperature=0.1)

# Define the prompt template
prompt_template = PromptTemplate(
    input_variables=["input", "agent_scratchpad"],
    template='''
    You are a NetBox specialist that helps manage network infrastructure data.

    You can query and update the NetBox CMDB to maintain an accurate record of devices, 
    interfaces, IP addresses, and other network components.

    **TOOLS:**
    {tools}

    To use a tool, follow this format:

    Thought: Do I need to use a tool? Yes
    Action: [Tool Name]
    Action Input: [Input to the tool]
    Observation: [Result of the tool]
    Final Answer: [Your response to the user]

    Begin!

    Question: {input}
    
    {agent_scratchpad}
    '''
)

# Create the agent
agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=prompt_template.partial(tools="\n".join([f"- {t.name}: {t.description}" for t in tools]))
)

# Initialize the agent executor
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    handle_parsing_errors=True,
    verbose=True
)