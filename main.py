import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from prompts import MASTER_PROMPT

def main():
    """
    Main function to set up and run our agent.
    """

    load_dotenv()
    if os.getenv("OPENAI_API_KEY") is None:
        raise ValueError("OPENAI_API_KEY environment variable not set.")
    
    llm = ChatOpenAI(model="gpt-4", temperature=0)

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", MASTER_PROMPT),
        ("human", "{user_input}")
    ])

    chain = prompt_template | llm

    print("Elenchus Agent is ready to assist you with mathematical problem-solving!")
    print("Running test query: 'I'm stuck on 'Prove the sum of the first n odd numbers.''")

    test_input = "I'm stuck on 'Prove the sum of the first n odd numbers.'"

    response = chain.invoke({"user_input": test_input})
    
    print("\n--- RAW MODEL OUTPUT ---")
    print(response.content)
    print("------------------------")


if __name__ == "__main__":
    main()
