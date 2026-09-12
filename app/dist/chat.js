const topTabs = [...document.querySelectorAll('[data-top-tab]')];
const topPanels = [...document.querySelectorAll('[data-top-panel]')];
const chatPanel = document.querySelector('#chat-panel');
const chatMessagesElement = document.querySelector('#chat-messages');
const chatForm = document.querySelector('#chat-form');
const chatInput = document.querySelector('#chat-input');
const chatSend = document.querySelector('#chat-send');
const chatStatus = document.querySelector('#chat-status');
const chatHistory = [];

// The app shell is intentionally compact HTML; move the chat panel to the main
// content area so it is a sibling of the movie panel before tab switching.
if (chatPanel) document.querySelector('main').append(chatPanel);

const chatEscape = value => String(value ?? '').replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[character]));

function selectTopTab(name, updateHash = true) {
  const selected = topTabs.some(tab => tab.dataset.topTab === name) ? name : 'library';
  for (const tab of topTabs) {
    const active = tab.dataset.topTab === selected;
    tab.setAttribute('aria-selected', String(active));
    tab.classList.toggle('is-active', active);
  }
  for (const panel of topPanels) panel.hidden = panel.dataset.topPanel !== selected;
  if (updateHash && window.location.hash !== `#${selected}`) window.location.hash = selected;
  if (selected === 'chat') chatInput?.focus();
}

function renderChat() {
  if (!chatHistory.length) {
    chatMessagesElement.innerHTML = '<div class="chat-empty">Ask anything about movies, or start with a recommendation question.</div>';
    return;
  }
  chatMessagesElement.innerHTML = chatHistory.map(message => `<div class="chat-message ${message.role}"><span class="chat-role">${message.role === 'user' ? 'You' : 'DeepSeek'}</span><div>${chatEscape(message.content)}</div></div>`).join('');
  chatMessagesElement.lastElementChild?.scrollIntoView({block: 'nearest'});
}

topTabs.forEach(tab => tab.addEventListener('click', () => selectTopTab(tab.dataset.topTab)));
window.addEventListener('hashchange', () => selectTopTab(window.location.hash.slice(1), false));

chatForm?.addEventListener('submit', async event => {
  event.preventDefault();
  const content = chatInput.value.trim();
  if (!content || chatSend.disabled) return;
  chatHistory.push({role: 'user', content});
  renderChat();
  chatInput.value = '';
  chatSend.disabled = true;
  chatStatus.textContent = 'Thinking…';
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({messages: chatHistory}),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Chat request failed.');
    chatHistory.push({role: 'assistant', content: payload.message});
    renderChat();
    chatStatus.textContent = '';
  } catch (error) {
    chatStatus.textContent = error.message;
  } finally {
    chatSend.disabled = false;
    chatInput.focus();
  }
});

selectTopTab(window.location.hash.slice(1), false);
