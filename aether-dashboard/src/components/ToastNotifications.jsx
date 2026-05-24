import React from 'react';
import { CheckCircle, AlertCircle, Info, X, Zap, Loader2 } from 'lucide-react';
import { useNotifications } from '../stateManager';

const ICONS = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertCircle,
  info: Info,
  running: Loader2,
};

const COLORS = {
  success: 'var(--accent)',
  error: 'var(--secondary)',
  warning: 'var(--warning)',
  info: 'var(--primary)',
  running: 'var(--primary)',
};

export default function ToastNotifications() {
  const { toasts, dismiss } = useNotifications();

  if (toasts.length === 0) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 16,
      right: 16,
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      maxWidth: 380,
    }}>
      {toasts.map(toast => {
        const Icon = ICONS[toast.type] || Info;
        const color = COLORS[toast.type] || COLORS.info;
        const isRunning = toast.type === 'running';

        return (
          <div
            key={toast.id}
            className="glass"
            style={{
              padding: '0.8rem 1rem',
              borderRadius: 10,
              background: 'rgba(10, 10, 20, 0.95)',
              border: `1px solid ${color}40`,
              borderLeft: `3px solid ${color}`,
              backdropFilter: 'blur(12px)',
              boxShadow: `0 4px 20px ${color}15`,
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
              animation: 'slideIn 0.3s ease-out',
            }}
          >
            <div style={{ marginTop: 1, flexShrink: 0 }}>
              <Icon
                size={16}
                color={color}
                className={isRunning ? 'spin' : ''}
              />
            </div>
            <div style={{ flex: 1, fontSize: '0.75rem', lineHeight: 1.5, color: 'var(--text)' }}>
              {toast.message}
            </div>
            <button
              onClick={() => dismiss(toast.id)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: 2,
                flexShrink: 0,
                opacity: 0.5,
              }}
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
