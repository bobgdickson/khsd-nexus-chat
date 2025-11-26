import { useEffect, useMemo, useState } from 'react';
import type { ChatKitOptions } from '@openai/chatkit';
import { ChatKit, useChatKit } from '@openai/chatkit-react';

import './App.css';

type StartScreenPrompt = {
  label: string;
  prompt: string;
};

type ChatKitUiConfig = {
  enabled: boolean;
  ready: boolean;
  apiUrl: string;
  domainKey: string;
  greeting: string;
  placeholder: string;
  startScreenPrompts: StartScreenPrompt[];
};

const AUTH_TOKEN = import.meta.env.VITE_CHATKIT_AUTH_TOKEN;
const USER_ID_HEADER = import.meta.env.VITE_CHATKIT_USER_ID ?? 'demo-user';
const CONFIG_URL =
  import.meta.env.VITE_CHATKIT_API_URL ??
  (import.meta.env.DEV ? 'http://localhost:8004/chatkit/config' : '/chatkit/config');
const CHATKIT_SCRIPT_SRC = 'https://cdn.platform.openai.com/deployments/chatkit/chatkit.js';

export default function App() {
  const [config, setConfig] = useState<ChatKitUiConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetch(CONFIG_URL, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`Failed to load ChatKit config: ${res.status}`);
        }
        const data = (await res.json()) as ChatKitUiConfig;
        setConfig(data);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError(err.message);
          setConfig(null);
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [CONFIG_URL]);

  if (loading) {
    return (
      <div className="app-shell">
        <header className="app-header">
          <div className="logo-wrap">
            <img src="/media/header_logo.png" alt="KHSD logo" className="app-logo" />
          </div>
          <div>
            <p className="eyebrow">KHSD Nexus Chat</p>
            <h1>Project SPARK Chatbot</h1>
          </div>
        </header>
        <main className="app-main">
          <p>Loading configuration…</p>
        </main>
      </div>
    );
  }

  if (error || !config) {
    return (
      <div className="app-shell">
        <header className="app-header">
          <div className="logo-wrap">
            <img src="/media/header_logo.png" alt="KHSD logo" className="app-logo" />
          </div>
          <div>
            <p className="eyebrow">KHSD Nexus Chat</p>
            <h1>Project SPARK Chatbot</h1>
          </div>
        </header>
        <main className="app-main">
          <p className="app-warnings">Failed to load ChatKit config: {error ?? 'Unknown error'}</p>
        </main>
      </div>
    );
  }

  if (!config.enabled || !config.ready) {
    return (
      <div className="app-shell">
        <header className="app-header">
          <div className="logo-wrap">
            <img src="/media/header_logo.png" alt="KHSD logo" className="app-logo" />
          </div>
          <div>
            <p className="eyebrow">KHSD Nexus Chat</p>
            <h1>Project SPARK Chatbot</h1>
          </div>
        </header>
        <main className="app-main">
          <section className="app-warnings">
            {!config.enabled && <p>ChatKit is disabled for this environment.</p>}
            {config.enabled && !config.ready && <p>ChatKit backend is not ready. Set OPENAI_API_KEY and restart.</p>}
          </section>
        </main>
      </div>
    );
  }

  return <ChatKitSurface config={config} />;
}

function ChatKitSurface({ config }: { config: ChatKitUiConfig }) {
  useEffect(() => {
    if (customElements.get('openai-chatkit')) {
      console.log('[chatkit] custom element already registered, skipping script injection');
      return;
    }
    const script = document.createElement('script');
    script.src = CHATKIT_SCRIPT_SRC;
    script.async = true;
    script.dataset.chatkitRuntime = 'true';
    console.log('[chatkit] injecting script', CHATKIT_SCRIPT_SRC);
    script.addEventListener('load', () => {
      console.log('[chatkit] script loaded', CHATKIT_SCRIPT_SRC);
    });
    script.addEventListener('error', (event) => {
      console.error('[chatkit] failed to load script', CHATKIT_SCRIPT_SRC, event);
    });
    document.head.appendChild(script);
    return () => {
      if (!customElements.get('openai-chatkit') && script.parentElement) {
        console.log('[chatkit] removing script before custom element registered');
        script.parentElement.removeChild(script);
      }
    };
  }, []);

  const apiConfig = useMemo<ChatKitOptions['api']>(() => {
    const fetchWithHeaders: typeof fetch = (url, options = {}) => {
      const headers = new Headers(options.headers ?? {});
      headers.set('x-user-id', USER_ID_HEADER);
      if (AUTH_TOKEN) {
        headers.set('Authorization', `Bearer ${AUTH_TOKEN}`);
      }
      return fetch(url, {
        ...options,
        headers,
      });
    };

    return {
      url: config.apiUrl,
      domainKey: config.domainKey,
      fetch: fetchWithHeaders,
      uploadStrategy: { type: 'two_phase' },
    };
  }, [config.apiUrl, config.domainKey]);

  const chatkit = useChatKit({
    api: apiConfig,
    startScreen: {
      greeting: config.greeting,
      prompts: config.startScreenPrompts,
    },
    composer: {
      placeholder: config.placeholder,
    },
    history: {
      enabled: true,
    },
    header: {
      enabled: true,
    },
    onError: ({ error }) => {
      console.error('ChatKit error', error);
    },
  });

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">KHSD Nexus Chat</p>
          <h1>Project SPARK Chatbot</h1>
          <p className="endpoint">Backend: {config.apiUrl}</p>
        </div>
        <div className="logo-wrap">
          <img src="/media/header_logo.png" alt="KHSD logo" className="app-logo" />
        </div>
      </header>
      <main className="app-main">
        <ChatKit ref={chatkit.ref} control={chatkit.control} className="chatkit-host" />
      </main>
    </div>
  );
}
