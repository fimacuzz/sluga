from flask import Flask, render_template

app = Flask(__name__)

# Данные для расписания (можно заменить на данные из базы данных)
schedule_data = [
    {"day": "Понедельник", "subject": "Математика", "time": "09:00 - 10:00", "teacher": "Иванова И.И."},
    {"day": "Вторник", "subject": "Физика", "time": "10:00 - 11:00", "teacher": "Петров П.П."},
]

# Данные для оценок
grades_data = [
    {"subject": "Математика", "grade": 5, "date": "10.10.2023", "comment": "Молодец!"},
    {"subject": "Физика", "grade": 4, "date": "11.10.2023", "comment": "Старайся больше."},
]

# Данные для домашних заданий
homework_data = [
    {"subject": "Математика", "task": "Решить задачи на стр. 45", "due_date": "15.10.2023"},
    {"subject": "Физика", "task": "Подготовить доклад", "due_date": "16.10.2023"},
]

@app.route('/')
def index():
    return render_template(
        'index.html',
        schedule=schedule_data,
        grades=grades_data,
        homework=homework_data
    )

if __name__ == '__main__':
    app.run(debug=True)