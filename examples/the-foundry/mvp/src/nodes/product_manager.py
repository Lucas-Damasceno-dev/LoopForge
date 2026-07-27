import os
from datetime import datetime, timezone
from typing import List
import json
from ..utils import Agent, StateKey
from ..llm_factory import get_llm_client

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage # Re-introduce BaseMessage import

# Utility to generate IDs (for demonstration, can be more robust)
def generate_user_story_id(epic_id: str, index: int) -> str:
    return f"{epic_id}-US{index+1:03d}"

# Define the Pydantic model for a User Story (based on user_story_schema.json)
class UserStorySchema(BaseModel):
    id: str = Field(..., description="Unique identifier for the user story, e.g., 'E-001-US001'.")
    title: str = Field(..., description="A short and descriptive title for the user story.")
    epic_id: str = Field(..., description="ID of the parent epic.")
    as_a: str = Field(..., description="The type of user or persona who will benefit from the story. E.g., 'motorista de van', 'pai de aluno'.")
    i_want_to: str = Field(..., description="The functionality the user wants to perform. E.g., 'rastrear a van em tempo real'.")
    so_that: str = Field(..., description="The value or benefit the user will get. E.g., 'saber onde meu filho está'.")
    acceptance_criteria: List[str] = Field(..., description="Clear acceptance criteria, preferably in 'Given-When-Then' format.")
    priority: str = Field(..., description="Priority of the user story. Possible values: 'Low', 'Medium', 'High', 'Critical'.")
    status: str = Field(..., description="Status of the user story. Possible values: 'Pending', 'In Progress', 'Done', 'Blocked'.")
    dates: dict = Field(..., description="Dates related to the user story lifecycle. E.g., {'created_at': 'ISO 8601 string'}")


# Define a wrapper Pydantic model for a list of User Stories
class UserStoryListSchema(BaseModel):
    stories: List[UserStorySchema] = Field(..., description="A list of user stories for the epic.")

# Mock data for Product Manager (User Stories)
MOCK_PM_USER_STORIES_DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'mocks', 'pm_user_stories.json')
with open(MOCK_PM_USER_STORIES_DATA_PATH, 'r', encoding='utf-8') as f:
    MOCK_PM_USER_STORIES_DATA = json.load(f)

def product_manager(state):
    """
    Recebe o estado, analisa o épico e gera as user stories.
    """
    print("---EXECUTANDO NÓ: Product Manager---")
    epic = state.get('epic')
    if not epic:
        raise ValueError("Épico não encontrado no estado para o Product Manager.")

    # Get current time for user story dates (defined unconditionally)
    now_iso = datetime.now(timezone.utc).isoformat()

    if state.get('mock_llm'):
        print("--- INFO: Product Manager operando em modo MOCK. Carregando user stories pré-definidas. ---")
        generated_user_stories_pydantic_wrapper = UserStoryListSchema(stories=[UserStorySchema(**us) for us in MOCK_PM_USER_STORIES_DATA])
        generated_user_stories_pydantic = generated_user_stories_pydantic_wrapper.stories
    else:
        # 1. Carrega o modelo de linguagem (LLM) configurado para saída estruturada
        # The LLM should output a list of UserStorySchema objects
        llm = get_llm_client(state['llm_provider'], state['llm_model_name'], temperature=0)

        # 2. Define o prompt para o Product Manager
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""Você é um Product Manager experiente. Sua tarefa é quebrar o épico fornecido em uma lista de user stories detalhadas, **em formato JSON**.
             Cada user story deve aderir estritamente ao seguinte esquema:
             
             - **id**: Identificador único da user story (use o padrão '{epic['id']}-USxxx', onde xxx é um número sequencial).
             - **title**: Título descritivo da user story.
             - **epic_id**: O ID do épico pai ('{epic['id']}').
             - **as_a**: Quem é o usuário/persona.
             - **i_want_to**: O que o usuário deseja fazer.
             - **so_that**: Qual o valor/benefício para o usuário.
                      - **acceptance_criteria**: Critérios de aceitação claros, **como uma lista de strings**, preferencialmente no formato 'Dado-Quando-Então'.
                      - **priority**: Prioridade da user story. Use 'Medium' como padrão.
                      - **status**: Status inicial. Use 'Pending' como padrão.
                      - **dates**: **Um objeto JSON** com `created_at` no formato ISO 8601.
             
                      Analise cuidadosamente o objetivo, escopo e valor de negócio do épico. Crie user stories que representem funcionalidades concretas.             Certifique-se de que cada user story tenha critérios de aceitação claros e mensuráveis.
             O output deve ser um objeto JSON contendo uma chave 'stories' que é uma lista de user stories.

             Aqui está o épico para ser quebrado:
             ---
             Título do Épico: {epic['title']}
             Descrição do Épico: {epic['description']}
             Objetivos de Negócio: {', '.join(epic['business_objectives'])}
             Hipótese: {', '.join(epic['hypothesis'])}
             Escopo (IN): {', '.join(epic['scope_in'])}
             Escopo (OUT): {', '.join(epic['scope_out'])}
             Métricas de Sucesso: {', '.join(epic['success_metrics'])}
             ---
             """),
            ("user", "Por favor, quebre este épico em user stories.")
        ])

        # 3. Cria a cadeia de processamento do LLM
        pm_chain = prompt | llm

        # 4. Invoca o LLM com o épico e gera as user stories
        llm_output = pm_chain.invoke({"epic": epic})
        
        # Check if the output is an AIMessage and extract content
        if isinstance(llm_output, BaseMessage) and llm_output.content:
            # Assuming the structured output is a JSON string in content
            parsed_content = json.loads(llm_output.content)
            generated_user_stories_pydantic_wrapper = UserStoryListSchema(**parsed_content)
        else:
            # Fallback or raise error if output is not as expected
            raise ValueError("Unexpected LLM output format for structured output.")
        generated_user_stories_pydantic = generated_user_stories_pydantic_wrapper.stories # Extract the list from the wrapper
    
    # Generate sequential IDs and convert to dict
    user_stories_dicts = []
    for i, us_pydantic in enumerate(generated_user_stories_pydantic):
        us_dict = us_pydantic.dict()
        us_dict['id'] = generate_user_story_id(epic['id'], i) # Override with sequential ID
        us_dict['epic_id'] = epic['id'] # Ensure epic_id is correct
        us_dict['dates']['created_at'] = now_iso # Assign created_at
        user_stories_dicts.append(us_dict)

    # 5. Atualiza o estado com as user stories geradas
    state['user_stories'] = user_stories_dicts
    
    # Save each generated user story to a file
    output_dir = state.get('output_dir')
    if output_dir:
        for us_dict in user_stories_dicts:
            us_id = us_dict['id']
            
            # Save as JSON
            us_json_filename = os.path.join(output_dir, f"us_{us_id}.json")
            with open(us_json_filename, 'w', encoding='utf-8') as f:
                json.dump(us_dict, f, indent=2, ensure_ascii=False)
            print(f"--- INFO: User Story '{us_id}' salva em: {us_json_filename} ---")

            # Save as Markdown
            us_md_filename = os.path.join(output_dir, f"us_{us_id}.md")
            with open(us_md_filename, 'w', encoding='utf-8') as f:
                f.write(f"# {us_dict['title']}\n\n")
                f.write(f"**ID:** {us_dict['id']}\n")
                f.write(f"**Épico:** {us_dict['epic_id']}\n\n")
                f.write(f"**Como um(a):** {us_dict['as_a']}\n")
                f.write(f"**Eu quero:** {us_dict['i_want_to']}\n")
                f.write(f"**Para que:** {us_dict['so_that']}\n\n")
                f.write("**Critérios de Aceitação:**\n")
                for criteria in us_dict['acceptance_criteria']:
                    f.write(f"- {criteria}\n")
                f.write(f"\n**Prioridade:** {us_dict['priority']}\n")
                f.write(f"**Status:** {us_dict['status']}\n")
                f.write(f"**Data de Criação:** {us_dict['dates']['created_at']}\n")
            print(f"--- INFO: User Story '{us_id}' salva em: {us_md_filename} ---")
    
    # 6. Define a transição para o próximo agente (Tech Lead)
    state[str(StateKey.NEXT_AGENT)] = Agent.TECH_LEAD.value
    return state