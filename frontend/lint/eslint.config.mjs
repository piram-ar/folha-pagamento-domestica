// Só o que derruba o app em execução é erro: nome inexistente passa pelo build do Vite e só aparece na tela.
import react from 'eslint-plugin-react';
import hooks from 'eslint-plugin-react-hooks';
import globals from 'globals';

export default [{
  files: ['src/**/*.{js,jsx}'],
  languageOptions: {
    ecmaVersion: 2023,
    sourceType: 'module',
    globals: globals.browser,
    parserOptions: { ecmaFeatures: { jsx: true } },
  },
  plugins: { react, 'react-hooks': hooks },
  rules: {
    'no-undef': 'error',
    'react/jsx-no-undef': 'error',
    'react/jsx-uses-vars': 'error',
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn',
    'no-unused-vars': 'warn',
  },
}];
