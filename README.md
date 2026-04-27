# VoxHire App

This is a full-stack application for conducting AI-powered interviews, designed to streamline the hiring process by providing automated, insightful, and unbiased candidate assessments.

## ✨ Features

- **AI-Powered Interviews**: Candidates interact with an AI interviewer that asks questions and records their responses.
- **Dynamic Question Generation**: The AI can generate job-specific questions based on the role and required skills.
- **Response Analysis**: Utilizes Natural Language Processing (NLP) to analyze candidate responses for clarity, relevance, and sentiment.
- **Transcription Services**: Automatically transcribes video or audio interviews into text.
- **Candidate Scoring**: Provides a scoring mechanism based on predefined metrics to help rank candidates.
- **User-Friendly Dashboard**: A clean interface for recruiters to set up interviews, view results, and manage candidates.

## 🛠️ Tech Stack

### Frontend
- **Framework**: React (with Next.js)
- **Styling**: Tailwind CSS
- **State Management**: Redux Toolkit

### Backend
- **Framework**: Node.js with Express.js
- **Database**: MongoDB with Mongoose
- **Authentication**: JSON Web Tokens (JWT)

### AI & Services
- **AI Model**: OpenAI's GPT-4 / Google Gemini
- **Speech-to-Text**: Whisper API

## 🚀 Getting Started

Follow these instructions to get a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

Make sure you have the following installed on your system:
- Node.js (v18.x or later)
- npm or yarn
- MongoDB

### Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/your-username/voxhire-app.git
    cd voxhire-app
    ```

2.  **Install backend dependencies:**
    ```sh
    cd server
    npm install
    ```

3.  **Install frontend dependencies:**
    ```sh
    cd ../client
    npm install
    ```

4.  **Set up environment variables:**
    Create a `.env` file in the `server` directory and add your configuration (e.g., database connection string, API keys).

## Usage

1.  **Start the backend server:**
    ```sh
    cd server
    npm run dev
    ```

2.  **Start the frontend development server:**
    ```sh
    cd client
    npm run dev
    ```

Open your browser and navigate to `http://localhost:3000` to see the application in action.

## 🤝 Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

Please read `CONTRIBUTING.md` for details on our code of conduct and the process for submitting pull requests.

## 📄 License

This project is licensed under the MIT License - see the `LICENSE.md` file for details.