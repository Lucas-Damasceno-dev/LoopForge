#-*- coding: utf-8 -*-
"""
Nó do Developer.
"""

import os
import re
from ..utils import Agent, StateKey
from ..llm_factory import get_llm_client # Import the factory

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Mock data for Developer
MOCK_DEV_CODE_DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'mocks', 'dev_code.py')
with open(MOCK_DEV_CODE_DATA_PATH, 'r', encoding='utf-8') as f:
    MOCK_DEV_CODE_DATA = f.read()


def developer(state):
    """
    Recebe o estado, analisa a especificação técnica e gera o código.
    """
    print("---EXECUTANDO NÓ: Developer---")
    
    tech_spec = state.get('tech_spec')
    if not tech_spec:
        raise ValueError("Especificação Técnica não encontrada no estado para o Developer.")

    if state.get('mock_llm'):
        print("--- INFO: Developer operando em modo MOCK. Carregando código pré-definido. ---")
        generated_code = MOCK_DEV_CODE_DATA
    else:
        llm = get_llm_client(state['llm_provider'], state['llm_model_name'], temperature=0)
        print(f"--- INFO: Developer usando LLM: {state['llm_provider']}/{state['llm_model_name']} ---")
        
        # Use StrOutputParser as the output is expected to be a plain string (the Python code)
        output_parser = StrOutputParser()

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Você é um Engenheiro de Software sênior, com foco em desenvolvimento back-end Python.
             Sua tarefa é gerar um arquivo Python completo, incluindo classes, funções, e uma seção `if __name__ == "__main__":` para demonstração, com base na especificação técnica fornecida.
             O código deve ser limpo, modular, e seguir as boas práticas de programação Python.
             Adicione comentários explicativos onde necessário.
             **Importante:** A saída deve ser APENAS o código Python, sem texto introdutório ou conclusivo.
             """),
            ("human", "Gere o código Python para a seguinte especificação técnica:\n{tech_spec}")
        ])

        developer_chain = prompt | llm | output_parser

        print("--- INFO: Gerando código com o LLM... ---")
        generated_code = developer_chain.invoke({"tech_spec": tech_spec})

    state['code'] = generated_code
    
    # Save the generated code to a file
    output_dir = state.get('output_dir')
    if output_dir:
        # Determine a simple filename for the code. This could be improved to infer from tech spec.
        # For now, let's just use a generic name or extract from a tech spec field if available.
        # Assuming the tech spec might contain an ID, use it for the filename
        tech_spec_id_match = re.search(r"ID:\s*([^\n]+)", tech_spec)
        tech_spec_id = tech_spec_id_match.group(1).strip() if tech_spec_id_match else "UNKNOWN_TECH_SPEC"
        
        code_filename = os.path.join(output_dir, f"code_{tech_spec_id}.py")
        with open(code_filename, 'w', encoding='utf-8') as f:
            f.write(generated_code)
        print(f"--- INFO: Código Python salvo em: {code_filename} ---")
    
    # Define a transição para o próximo agente.
    state[str(StateKey.NEXT_AGENT)] = Agent.QA.value
    return state
