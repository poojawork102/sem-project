/**
 * Northstar University — DSADPS AI Admin Chatbot Widget
 * Floating chat interface powered by Google Gemini
 */

(function () {
  'use strict';

  const SUGGESTED_CHIPS = [
    'Show risk summary',
    'Top suspicious IPs',
    'Blocked apps today',
    'Program distribution',
    'High risk applicants',
  ];

  let chatHistory = [];
  let isOpen = false;
  let isLoading = false;

  // ---------------------------------------------------------------
  // Inject Chat Widget HTML
  // ---------------------------------------------------------------
  function injectWidget() {
    // FAB button
    const fab = document.createElement('button');
    fab.className = 'chat-fab';
    fab.id = 'chatFab';
    fab.setAttribute('title', 'AI Assistant');
    fab.innerHTML = `
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
      </svg>
    `;

    // Chat panel
    const panel = document.createElement('div');
    panel.className = 'chat-panel';
    panel.id = 'chatPanel';
    panel.innerHTML = `
      <div class="chat-header">
        <div class="chat-header-avatar">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
          </svg>
        </div>
        <div class="chat-header-info">
          <span class="chat-header-title">DSADPS AI Assistant</span>
          <span class="chat-header-subtitle">Powered by Gemini &bull; Ask about your data</span>
        </div>
        <button class="chat-close-btn" id="chatCloseBtn" title="Close chat">
          <svg style="width: 18px; height: 18px;" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="chat-messages" id="chatMessages">
        <div class="chat-welcome">
          <div class="chat-welcome-icon">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <h4>Northstar AI Assistant</h4>
          <p>Ask me anything about your admissions data, risk trends, or security intelligence.</p>
        </div>
        <div class="chat-chips" id="chatChips">
          ${SUGGESTED_CHIPS.map(c => `<button class="chat-chip" data-chip="${c}">${c}</button>`).join('')}
        </div>
      </div>

      <div class="chat-input-area">
        <input type="text" class="chat-input" id="chatInput" placeholder="Ask about your data..." maxlength="2000" />
        <button class="chat-send-btn" id="chatSendBtn" title="Send message">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </div>
    `;

    document.body.appendChild(fab);
    document.body.appendChild(panel);

    // Bind events
    fab.addEventListener('click', toggleChat);
    document.getElementById('chatCloseBtn').addEventListener('click', toggleChat);
    document.getElementById('chatSendBtn').addEventListener('click', sendMessage);
    document.getElementById('chatInput').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    // Chip click handlers
    document.querySelectorAll('.chat-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const text = chip.getAttribute('data-chip');
        document.getElementById('chatInput').value = text;
        sendMessage();
      });
    });
  }

  // ---------------------------------------------------------------
  // Toggle Chat Open / Close
  // ---------------------------------------------------------------
  function toggleChat() {
    isOpen = !isOpen;
    const fab = document.getElementById('chatFab');
    const panel = document.getElementById('chatPanel');

    if (isOpen) {
      fab.classList.add('open');
      panel.classList.add('open');
      document.getElementById('chatInput').focus();
    } else {
      fab.classList.remove('open');
      panel.classList.remove('open');
    }
  }

  // ---------------------------------------------------------------
  // Send Message
  // ---------------------------------------------------------------
  async function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message || isLoading) return;

    input.value = '';
    isLoading = true;

    // Hide welcome and chips on first message
    const welcome = document.querySelector('.chat-welcome');
    const chips = document.getElementById('chatChips');
    if (welcome) welcome.style.display = 'none';
    if (chips) chips.style.display = 'none';

    // Add user message
    appendMessage('user', message);
    chatHistory.push({ role: 'user', content: message });

    // Show typing indicator
    const typingEl = showTyping();

    // Disable send button
    const sendBtn = document.getElementById('chatSendBtn');
    sendBtn.disabled = true;

    try {
      const result = await Api.sendChatMessage(message, chatHistory.slice(-10));
      removeTyping(typingEl);

      const response = result.response || 'No response received.';
      appendMessage('assistant', response, result.source === 'error' ? 'error' : 'assistant');
      chatHistory.push({ role: 'assistant', content: response });

    } catch (err) {
      removeTyping(typingEl);
      const errorMsg = err.message || 'Failed to get a response. Check your connection and API key.';
      appendMessage('error', errorMsg);
    } finally {
      isLoading = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  // ---------------------------------------------------------------
  // Render Messages
  // ---------------------------------------------------------------
  function appendMessage(role, text, extraClass = '') {
    const container = document.getElementById('chatMessages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-msg ${role} ${extraClass}`.trim();

    const bubble = document.createElement('div');
    bubble.className = 'chat-msg-bubble';

    if (role === 'assistant' || role === 'error') {
      bubble.innerHTML = renderMarkdown(text);
    } else {
      bubble.textContent = text;
    }

    msgDiv.appendChild(bubble);
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
  }

  function showTyping() {
    const container = document.getElementById('chatMessages');
    const typing = document.createElement('div');
    typing.className = 'chat-typing';
    typing.id = 'chatTypingIndicator';
    typing.innerHTML = `
      <div class="chat-typing-dot"></div>
      <div class="chat-typing-dot"></div>
      <div class="chat-typing-dot"></div>
    `;
    container.appendChild(typing);
    container.scrollTop = container.scrollHeight;
    return typing;
  }

  function removeTyping(el) {
    if (el && el.parentElement) {
      el.parentElement.removeChild(el);
    }
  }

  // ---------------------------------------------------------------
  // Basic Markdown Renderer
  // ---------------------------------------------------------------
  function renderMarkdown(text) {
    if (!text) return '';
    let html = text
      // Escape HTML
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      // Bold
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      // Italic
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      // Inline code
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      // Bullet lists
      .replace(/^[\s]*[-*]\s+(.+)$/gm, '<li>$1</li>')
      // Numbered lists
      .replace(/^[\s]*\d+\.\s+(.+)$/gm, '<li>$1</li>')
      // Wrap consecutive <li> in <ul>
      .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
      // Line breaks
      .replace(/\n\n/g, '<br/><br/>')
      .replace(/\n/g, '<br/>');

    return html;
  }

  // ---------------------------------------------------------------
  // Initialize when DOM is ready
  // ---------------------------------------------------------------
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectWidget);
  } else {
    injectWidget();
  }
})();
