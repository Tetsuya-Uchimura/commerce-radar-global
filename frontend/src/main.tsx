import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import './global.css';
// Keep sessions, local persona storage, and PayPal return URLs on one origin.
if(location.hostname==='127.0.0.1'&&location.port==='5173'){
 location.replace('http://localhost:5173'+location.pathname+location.search+location.hash);
}else{
 createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
}
