
# main.py - Simulação de código para o épico E-001 (MOCK)

class VanTracker:
    def __init__(self, driver_id):
        self.driver_id = driver_id
        self.students = {} # {student_id: {'name': '...', 'address': '...', 'confirmed': False}}
        self.route = []
        self.current_location = None

    def add_student(self, student_id, name, address):
        self.students[student_id] = {'name': name, 'address': address, 'confirmed': False}
        print(f"Aluno {name} adicionado.")

    def confirm_presence(self, student_id, confirmed=True):
        if student_id in self.students:
            self.students[student_id]['confirmed'] = confirmed
            print(f"Presença de {self.students[student_id]['name']} confirmada: {confirmed}.")
        else:
            print(f"Aluno com ID {student_id} não encontrado.")

    def generate_route(self):
        confirmed_students = [s for s_id, s in self.students.items() if s['confirmed']]
        if not confirmed_students:
            print("Nenhum aluno confirmado para gerar rota.")
            self.route = []
            return

        # Simula a otimização de rota: apenas ordena por nome por simplicidade
        self.route = sorted(confirmed_students, key=lambda x: x['name'])
        print("Rota gerada:", [s['name'] for s in self.route])

    def start_route(self):
        if not self.route:
            print("Nenhuma rota para iniciar. Gere a rota primeiro.")
            return
        print("Rota iniciada. Enviando notificações...")
        # Simula notificações aos pais
        for student in self.route:
            print(f"Notificação para pais de {student['name']}: Van a caminho.")
        self.current_location = "Ponto de Partida" # Simula a localização inicial

    def update_location(self, new_location):
        self.current_location = new_location
        print(f"Localização da van atualizada para: {new_location}.")
        # Simula envio de localização em tempo real para pais

    def get_status(self):
        return {
            "driver_id": self.driver_id,
            "current_location": self.current_location,
            "next_stop": self.route[0]['name'] if self.route else "N/A",
            "students_on_board": [s['name'] for s in self.students.values() if s.get('on_board', False)]
        }

if __name__ == "__main__":
    van = VanTracker("DRV001")
    van.add_student("S001", "Alice", "Rua A")
    van.add_student("S002", "Bruno", "Rua B")
    van.add_student("S003", "Carla", "Rua C")

    van.confirm_presence("S001", True)
    van.confirm_presence("S003", True)

    van.generate_route()
    van.start_route()
    van.update_location("Rua A - Próximo à casa da Alice")
