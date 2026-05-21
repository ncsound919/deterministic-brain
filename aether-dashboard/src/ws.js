/* ═══════════════════════════════════════════════════════════════
   WebSocket Client — streaming chat with hermes via brain API
   ═══════════════════════════════════════════════════════════════ */

export function createChatWebSocket(onMessage, onError, onOpen, onClose) {
  const ws = new WebSocket('ws://localhost:8000/ws/chat');
  let reconnectTimer = null;

  ws.onopen = () => {
    console.log('[WS] Connected');
    if (onOpen) onOpen();
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (onMessage) onMessage(data);
    } catch {
      if (onMessage) onMessage({ text: event.data });
    }
  };

  ws.onerror = (error) => {
    console.error('[WS] Error:', error);
    if (onError) onError(error);
  };

  ws.onclose = () => {
    console.log('[WS] Disconnected');
    if (onClose) onClose();
    // Auto-reconnect after 3s
    reconnectTimer = setTimeout(() => {
      console.log('[WS] Reconnecting...');
      createChatWebSocket(onMessage, onError, onOpen, onClose);
    }, 3000);
  };

  return {
    send: (text) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ text }));
      }
    },
    close: () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws.close();
    },
  };
}
