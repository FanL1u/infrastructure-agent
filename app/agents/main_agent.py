import os
import logging
import streamlit as st
from langchain.agents import initialize_agent, Tool
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# Import our agent modules
from agents.device1_agent import agent_executor as device1_agent
from agents.device2_agent import agent_executor as device2_agent  
from agents.netbox_agent import agent_executor as netbox_agent

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize the LLM
llm = ChatOpenAI(model_name="gpt-4o", temperature=0.1)

# Define agent functions
def device1_agent_func(input_text: str) -> str:
    return device1_agent.invoke(f"device1: {input_text}")

def device2_agent_func(input_text: str) -> str:
    return device2_agent.invoke(f"device2: {input_text}")

def netbox_agent_func(input_text: str) -> str:
    return netbox_agent.invoke(input_text)

# Define LangChain Tools
device1_tool = Tool(
    name="Device1 Agent", 
    func=device1_agent_func, 
    description="Use for commands on Device1 (Linux host)."
)

device2_tool = Tool(
    name="Device2 Agent", 
    func=device2_agent_func, 
    description="Use for commands on Device2 (Linux host)."
)

netbox_tool = Tool(
    name="NetBox Agent", 
    func=netbox_agent_func, 
    description="Use for NetBox operations and queries."
)

# Create main agent
tools = [device1_tool, device2_tool, netbox_tool]
main_agent = initialize_agent(
    tools=tools, 
    llm=llm, 
    agent="zero-shot-react-description", 
    verbose=True
)

# Setup Streamlit UI
st.title("Infrastructure Agent")

# Create a chat interface
if "messages" not in st.session_state:
    st.session_state.messages = []

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
    
    # Get response from the agent
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = main_agent.invoke(prompt)
            response_text = response.get("output", "I encountered an issue processing your request.")
            st.markdown(response_text)
    
    # Store assistant response
    st.session_state.messages.append({"role": "assistant", "content": response_text})