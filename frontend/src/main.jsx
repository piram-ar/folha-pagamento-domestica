import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './AuthContext';
import { FeedbackProvider } from './components/feedback';
import './styles.css';

// Roda do mouse sobre um campo numérico em foco mudaria o valor sem a pessoa perceber
document.addEventListener('wheel', () => {
  const campo = document.activeElement;
  if (campo?.type === 'number') campo.blur();
}, { passive: true });

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <FeedbackProvider>
          <App />
        </FeedbackProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
