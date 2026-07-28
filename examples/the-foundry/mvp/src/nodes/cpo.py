import json
import os
from datetime import UTC, datetime

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from ..llm_factory import get_llm_client
from ..utils import Agent, StateKey


# Define Pydantic models for structured output
class Stakeholders(BaseModel):
    owner: str = Field(..., description="The agent/role that is the owner of the initiative (normally, CPO).")
    consulted: list[str] = Field(..., description="List of agents/roles that should be consulted.")

class Dates(BaseModel):
    created_at: str = Field(..., description="Date and time of epic creation in ISO 8601 format.")
    started_at: str = Field(..., description="Date and time when work on the epic was started in ISO 8601 format.")
    completed_at: str | None = Field(None, description="Date and time when all work for the epic was completed in ISO 8601 format.")

class EpicSchema(BaseModel):
    id: str = Field(..., description="Unique identifier for the epic (format: E-XXX).")
    title: str = Field(..., description="A short, descriptive title for the epic.")
    description: str = Field(..., description="A description of the business problem to be solved.")
    business_objectives: list[str] = Field(..., description="List of business goals this epic aims to achieve.")
    hypothesis: str = Field(..., description="The hypothesis that will be validated with the delivery of this epic.")
    scope_in: list[str] = Field(..., description="List of items that are IN scope for this epic.")
    scope_out: list[str] = Field(..., description="List of items that are OUT of scope for this epic.")
    success_metrics: list[str] = Field(..., description="Metrics that will be used to measure the success of the epic.")
    stakeholders: Stakeholders
    dates: Dates

# Mock data for CPO
MOCK_CPO_EPIC_DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'mocks', 'cpo_epic.json')
with open(MOCK_CPO_EPIC_DATA_PATH, 'r', encoding='utf-8') as f:
    MOCK_CPO_EPIC_DATA = json.load(f)

def cpo(state):
    """
    Recebe a ideia inicial do usuário e a transforma em um épico estruturado.
    """
    print("---EXECUTANDO NÓ: CPO---")
    
    if state.get('mock_llm'):
        print("--- INFO: CPO operando em modo MOCK. Carregando épico pré-definido. ---")
        generated_epic = MOCK_CPO_EPIC_DATA
    else:
        # Get current time for epic dates (only for actual LLM generation)
        now_iso = datetime.now(UTC).isoformat()

        # 1. Carrega o modelo de linguagem (LLM) configurado para saída estruturada
        llm = get_llm_client(state['llm_provider'], state['llm_model_name'], temperature=0)
        print(f"--- INFO: CPO usando LLM: {state['llm_provider']}/{state['llm_model_name']} ---")
        
        llm = llm.with_structured_output(EpicSchema)

        # 2. Define o prompt para o CPO
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Você é um CPO (Chief Product Officer) experiente e tem a tarefa de transformar uma ideia bruta do usuário em um épico de produto bem estruturado **em formato JSON**.
             A saída JSON deve aderir estritamente ao esquema de saída esperado para o épico.
             
             Preencha todos os campos obrigatórios.
             Foque no valor de negócio e na experiência do usuário.
             Para 'id', crie um identificador único como 'E-001'.
             Para 'stakeholders.owner', use 'CPO'. Para 'stakeholders.consulted', liste 'Product Manager', 'UX/UI Designer', 'CTO'.
             Para 'dates.created_at' e 'dates.started_at', use a data e hora atual no formato ISO 8601.
             Não inclua informações sobre como implementar a solução, apenas 'o quê' e 'porquê'.
             Lembre-se da sua missão de atuar como parceiro de descoberta, fazendo perguntas de sondagem e utilizando o framework 'Jobs to Be Done' para garantir que o épico reflita uma necessidade real e um progresso desejado pelo cliente.
             """),
            ("user", "Ideia do usuário: {idea}")
        ])

        # 3. Cria a cadeia de processamento do LLM
        cpo_chain = prompt | llm

        # 4. Invoca o LLM com a ideia do estado
        idea = state.get('idea', '')
        generated_epic_pydantic = cpo_chain.invoke({"idea": idea})
        generated_epic = generated_epic_pydantic.dict() # Convert Pydantic object to dict

        # Manually set dates to avoid cache busting
        generated_epic['dates']['created_at'] = now_iso
        generated_epic['dates']['started_at'] = now_iso


    # 5. Atualiza o estado com o épico gerado
    state['epic'] = generated_epic
    
    # Save the generated epic to a file
    output_dir = state.get('output_dir')
    if output_dir:
        epic_filename = os.path.join(output_dir, f"epic_{generated_epic['id']}.json")
        with open(epic_filename, 'w', encoding='utf-8') as f:
            json.dump(generated_epic, f, indent=2, ensure_ascii=False)
        print(f"--- INFO: Épico salvo em: {epic_filename} ---")
    
    # 6. Define a transição para o próximo agente (Product Manager)
    state[str(StateKey.NEXT_AGENT)] = Agent.PRODUCT_MANAGER.value
    return state
