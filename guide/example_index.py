ANSWERS = {
    "понедельник": "В понедельник с 17:00 до 19:00 логоритмика.",
    "вторник": "Во вторник с 16:30 до 17:30 танцы.",
    "танц": "Танцы во вторник и четверг в 16:30.",
}

def handler(event, context):
    text = event["request"]["command"].lower()
    if not text:
        reply = "Привет! Спросите про день недели или занятие."
    else:
        reply = "Не поняла. Спросите, например: что во вторник?"
        for word, answer in ANSWERS.items():
            if word in text:
                reply = answer
                break
    return {
        "version": event["version"],
        "response": {"text": reply, "end_session": False},
    }
