# Coding Agent

Минимальный агент-помощник для программирования, который общается с LLM через OpenAI-compatible API и выполняет команды bash.

Смотри YouTube-видео о разработке этого агента [https://www.youtube.com/watch?v=H7FSTj4x4xQ](https://www.youtube.com/watch?v=H7FSTj4x4xQ).

## Возможности

- **Tool calling** — модель вызывает инструменты (по умолчанию `bash`)
- **Цикл взаимодействия** — агент может вызывать инструменты, пока не решит задачу
- **OpenAI-compatible API** — работает с Ollama, vLLM, LM Studio и любыми серверами с OpenAI-совместимым интерфейсом
- **Без зависимостей от SDK** — только `requests`, никаких обёрток

## Быстрый старт

```bash
# Установить зависимости
uv sync

# Передать задачу аргументом
python chebupelka.py "Напиши скрипт на Python, который рекурсивно найдёт все .py файлы в текущей директории"
```

## Конфигурация

В `chebupelka.py` настройте подключение к LLM:

| Переменная     | Описание                          |
|----------------|-----------------------------------|
| `BASE_URL`     | URL вашего LLM-сервера            |
| `API_KEY`      | Ключ авторизации                  |
| `MODEL`        | Имя модели                        |

### Пример с Ollama

```python
BASE_URL = "http://localhost:11434/v1"
API_KEY   = "ollama"  # или любой строковый ключ
MODEL      = "qwen3.6-35b-a3b"
```

## Как это работает

```
Пользователь → Agent Loop → LLM (chat/completions API)
                        ↕
              Tool calls (bash)
                        ↓
                  Результат команды
                        ↑
              Возврат в цикл с результатом
```

1. Пользователь вводит задачу
2. Агент отправляет историю сообщений в LLM
3. Если модель хочет вызвать инструмент — результат выполняется локально (`subprocess.run`)
4. Результат возвращается модели, цикл повторяется
5. Когда модель перестаёт вызывать инструменты — задача завершена

## Расширение инструментов

Добавьте новый инструмент в `TOOLS_MAP` и опишите его в `TOOLS`:

```python
# В TOOLS:
{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the contents of a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path."},
            },
            "required": ["path"],
        },
    }
}

# В TOOLS_MAP:
TOOLS_MAP = {
    "bash": run_bash,
    "read_file": read_file,  # добавить функцию
}
```

## Зависимости

- Python ≥ 3.10
- `requests` — единственная runtime-зависимость
