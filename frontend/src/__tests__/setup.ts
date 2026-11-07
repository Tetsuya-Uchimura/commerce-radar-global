import '@testing-library/jest-dom/vitest';
import {afterEach} from 'vitest';
import {cleanup,configure} from '@testing-library/react';
// Production discovery deliberately debounces 650ms after initial data hydration.
configure({asyncUtilTimeout:4000});
afterEach(()=>{cleanup();localStorage.clear();sessionStorage.clear();window.history.replaceState({},'','/');});
