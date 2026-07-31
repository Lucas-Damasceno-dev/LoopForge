"""FlakeIsolator: Disjuntor de Testes Flaky em Tempo Real para o nó QA."""

import os
import subprocess


class FlakeIsolator:
    def __init__(self, project_dir: str):
        self.project_dir = os.path.abspath(project_dir)

    def is_preexisting_flake(self, test_name: str, test_cmd: str) -> bool:
        """Executa o teste específico para verificar se ele falha de forma oscilante / pré-existente."""
        if not test_cmd:
            return False

        try:
            # Re-executar o teste isolado 2 vezes para checar não-determinismo
            results = []
            for _ in range(2):
                res = subprocess.run(
                    test_cmd,
                    shell=True,
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                results.append(res.returncode)

            # Se os resultados variarem entre tentativas ou falharem consistentemente por ambiente
            if len(set(results)) > 1:
                return True
        except Exception:
            pass

        return False

    def filter_flaky_failures(self, failed_tests: list[dict], test_cmd: str) -> tuple[list[dict], list[dict]]:
        """Separa falhas legítimas de falhas pré-existentes / flaky."""
        legitimate = []
        flaky = []

        for ft in failed_tests:
            test_name = ft.get("name", "")
            if self.is_preexisting_flake(test_name, test_cmd):
                flaky.append(ft)
            else:
                legitimate.append(ft)

        return legitimate, flaky
