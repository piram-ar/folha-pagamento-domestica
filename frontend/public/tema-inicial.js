// Aplica o tema salvo antes do primeiro desenho da tela (evita piscar claro no modo escuro).
// Arquivo separado (e não <script> inline) para a política de segurança (CSP) poder proibir scripts inline.
try {
  var tema = localStorage.getItem('folha_tema');
  if (tema === 'escuro') document.documentElement.dataset.theme = 'dark';
  else if (tema === 'claro') document.documentElement.dataset.theme = 'light';
} catch (e) { /* sem localStorage: segue o tema do sistema */ }
