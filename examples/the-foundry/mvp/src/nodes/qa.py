"""
Nó do QA.
"""
import json
import os
from datetime import UTC, datetime

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from ..llm_factory import get_llm_client  # Import the factory
from ..utils import Agent, StateKey


# --- Pydantic Models for Test Execution Report ---
class Environment(BaseModel):
    name: str = Field(..., description="The environment where the tests ran (e.g., 'local', 'ci', 'staging', 'production').")
    config_hash: str | None = Field(None, description="Hash of the configuration/environment variables used. Helps debug 'it works on my machine' issues.")

class FailedTestDetails(BaseModel):
    test_name: str
    error_message: str
    stack_trace_snippet: str | None = None
    is_flaky: bool = False

class ResultsBySuite(BaseModel):
    suite_name: str
    suite_type: str = Field(..., description="Type of test suite (e.g., 'unit', 'integration', 'e2e', 'contract', 'performance').")
    status: str = Field(..., description="Status of the test suite ('PASS', 'FAIL', 'SKIP').")
    duration_seconds: float
    total_tests: int
    failed_tests_details: list[FailedTestDetails] = Field(default_factory=list)

class Summary(BaseModel):
    status: str = Field(..., description="Overall status ('PASS', 'FAIL', 'UNSTABLE'). 'UNSTABLE' is useful for flaky tests.")
    total_tests: int
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    flaky_tests_detected: int = 0
    duration_seconds: float

class CodeCoverage(BaseModel):
    provider: str
    report_url: str | None = None
    metrics: dict
    threshold_met: bool = False

class Artifacts(BaseModel):
    logs_url: str | None = None
    screenshots_url: list[str] | None = None

class TestExecutionReportSchema(BaseModel):
    id: str = Field(..., description="Unique ID for the test execution (e.g., 'EXEC-2023-10-27-001').")
    user_story_id: str = Field(..., description="ID of the user story tested.")
    commit_hash: str = Field(..., description="The commit hash tested (Crucial for bisecting).")
    execution_timestamp: str = Field(..., description="ISO 8601 timestamp of execution.")
    executed_by: str = Field(..., description="ID of the QA or CI Tool (e.g., 'qa.agent', 'jenkins-agent-01').")
    environment: Environment
    summary: Summary
    results_by_suite: list[ResultsBySuite] = Field(default_factory=list)
    code_coverage: CodeCoverage | None = None
    artifacts: Artifacts | None = None

# Mock data for QA
MOCK_QA_TEST_REPORT_DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'mocks', 'qa_test_report.json')
with open(MOCK_QA_TEST_REPORT_DATA_PATH, 'r', encoding='utf-8') as f:
    MOCK_QA_TEST_REPORT_DATA = json.load(f)

def qa(state):
    """
    Recebe o estado, analisa o código e gera o relatório de testes.
    """
    print("---EXECUTANDO NÓ: QA---")
    
    code = state.get('code')
    user_stories = state.get('user_stories')
    if not code:
        raise ValueError("Código não encontrado no estado para o QA.")
    if not user_stories:
        raise ValueError("User Stories não encontradas no estado para o QA.")

    # Get current time for test report dates
    now_iso = datetime.now(UTC).isoformat()
    # Simple ID generation for now. Could be more robust.
    report_id = f"EXEC-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}-001"
    
    # Take the ID of the first user story as the primary one for the report
    user_story_id = user_stories[0]['id'] if user_stories else "UNKNOWN_US"

    if state.get('mock_llm'):
        print("--- INFO: QA operando em modo MOCK. Carregando relatório de testes pré-definido. ---")
        generated_test_report = MOCK_QA_TEST_REPORT_DATA
        generated_test_report['id'] = report_id
        generated_test_report['user_story_id'] = user_story_id
        generated_test_report['execution_timestamp'] = now_iso
    else:
        llm = get_llm_client(state['llm_provider'], state['llm_model_name'], temperature=0)
        print(f"--- INFO: QA usando LLM: {state['llm_provider']}/{state['llm_model_name']} ---")
        
        llm_with_structured_output = llm.with_structured_output(TestExecutionReportSchema)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """Você é um Engenheiro de QA (Quality Assurance) sênior.
             Sua tarefa é analisar o código Python fornecido, junto com as User Stories que ele se propõe a implementar, e gerar um relatório de execução de testes abrangente em formato JSON.
             O relatório deve aderir estritamente ao esquema de saída esperado para TestExecutionReportSchema.
             
             Simule a execução de testes unitários e de integração, buscando identificar possíveis falhas, cobertura de código e falhas de design.
             Seja crítico e detalhado na seção `results_by_suite` para listar os testes que você 'executou' e seus 'resultados'.
             Preencha todos os campos obrigatórios.
             Para o 'id' do relatório, use o formato 'EXEC-YYYY-MM-DD-HHMMSS-XXX'.
             Para 'user_story_id', use o ID da User Story principal que este código implementa.
             Para 'commit_hash', use um valor genérico como 'mock_commit_hash' para este exercício.
             Para 'executed_by', use 'qa.agent'.
             Para 'execution_timestamp', use a data e hora atual no formato ISO 8601.
             """),
            ("human", "Analise o seguinte código:\n```python\n{code}\n```\n\nE estas são as User Stories relacionadas:\n{user_stories_str}\n\nPor favor, gere um relatório de execução de testes detalhado.")
        ])

        # Convert user_stories (list of dicts) to a formatted string for the prompt
        user_stories_str = "\n".join([json.dumps(us, indent=2, ensure_ascii=False) for us in user_stories])
        
        qa_chain = prompt | llm_with_structured_output

        print("--- INFO: Gerando relatório de testes com o LLM... ---")
        generated_test_report_pydantic = qa_chain.invoke({"code": code, "user_stories_str": user_stories_str})
        generated_test_report = generated_test_report_pydantic.dict()

        # Manually set dynamic fields after generation
        generated_test_report['id'] = report_id
        generated_test_report['user_story_id'] = user_story_id
        generated_test_report['execution_timestamp'] = now_iso

    state['test_report'] = generated_test_report
    
    # Save the generated test report to a file
    output_dir = state.get('output_dir')
    if output_dir:
        test_report_filename = os.path.join(output_dir, f"test_report_{generated_test_report['id']}.json")
        with open(test_report_filename, 'w', encoding='utf-8') as f:
            json.dump(generated_test_report, f, indent=2, ensure_ascii=False)
        print(f"--- INFO: Relatório de Testes salvo em: {test_report_filename} ---")
    
    # Define a transição para o estado final do grafo.
    state[str(StateKey.NEXT_AGENT)] = Agent.FINISH.value
    return state
