const chatHistory = document.getElementById('chat-history');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');

let currentSessionId = null;

function addMessageToHistory(message, sender) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', `${sender}-message`);
    messageElement.innerText = message;
    chatHistory.appendChild(messageElement);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

async function sendMessage() {
    const messageText = userInput.value.trim();
    if (messageText === '') return;

    addMessageToHistory(messageText, 'user');
    userInput.value = '';

    // IMPORTANT: This URL must point to your ngrok tunnel
    const backendUrl = 'https://8af13e42769a.ngrok-free.app/chat';

    try {
        const response = await fetch(backendUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: messageText, session_id: currentSessionId })
        });

        if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);

        const data = await response.json();
        currentSessionId = data.session_id;
        addMessageToHistory(data.response, 'bot');

    } catch (error) {
        console.error('Error:', error);
        addMessageToHistory('Sorry, I am having trouble connecting to the server.', 'bot');
    }
}

sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

// Initial greeting
addMessageToHistory('Hello! I am the I4C Cybercrime Reporting Assistant. How can I help you?', 'bot');