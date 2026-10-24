# AI Query Assistant 🤖

An AI-powered chatbot built using Python, Flask, and Google's Gemini API. It allows users to ask questions and receive AI-generated responses through a simple web interface.

## ✨ Features

- AI-powered question answering using Gemini
- Interactive web interface
- Flask backend for processing user requests
- Environment variable support for API key configuration
- Python-based application

## 🛠️ Tech Stack

- **Language:** Python
- **Backend:** Flask
- **AI Integration:** Google Gemini API
- **Environment Management:** python-dotenv
- **Frontend:** HTML, CSS, JavaScript

## 📁 Project Structure

```text
AI-Query-Assistant/
├── app.py
├── database.py
├── test_gemini.py
├── requirements.txt
├── .env
├── static/
│   └── script.js
└── templates/
    └── index.html
```

*Note: The structure above is illustrative. Update it to match your actual project files. Do not upload your `.env` file to GitHub.*

## ⚙️ Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/Pasupuletibhanupriya/AI-Query-Assistant.git
cd AI-Query-Assistant
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the Gemini API key

Create a `.env` file in the project root and add your own API key:

```env
GEMINI_API_KEY=your_api_key_here
```

Replace `your_api_key_here` with your actual Gemini API key. Never share or commit this key to GitHub.

### 5. Run the application

```bash
python app.py
```

Open the local URL displayed in your terminal, commonly `http://127.0.0.1:5000`, in your browser.

## 🔐 Security

- Keep API keys private.
- Store secrets in environment variables.
- Exclude `.env` and `venv/` from Git using `.gitignore`.

## 🎯 Purpose

This project was developed to learn how AI-powered chatbots work and how to integrate a generative AI model into a web application.

## 👩‍💻 Author

**Bhanu Priya Pasupuleti**

- GitHub: [Pasupuletibhanupriya](https://github.com/Pasupuletibhanupriya)
