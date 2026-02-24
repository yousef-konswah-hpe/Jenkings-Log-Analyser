
import React, { useState } from 'react';
import './App.css';

function App() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // For now, I am just showing the question as the answer testing the new UI
    setAnswer(`You asked: ${question}`);
  };

  return (
    <div className="App">
      <h1>AI Chatbot</h1>
      <form onSubmit={handleSubmit} style={{ marginBottom: '1rem' }}>
        <input
          type="text"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          placeholder="Ask a question..."
          style={{ width: '300px', padding: '8px' }}
        />
        <button type="submit" style={{ marginLeft: '8px', padding: '8px 16px' }}>
          Send
        </button>
      </form>
      <div style={{ minHeight: '40px', border: '1px solid #ccc', padding: '12px', borderRadius: '4px', background: '#f9f9f9' }}>
        {answer ? <strong>Answer:</strong> : null} {answer}
      </div>
    </div>
  );
}

export default App;
