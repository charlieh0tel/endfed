// Ambient shims for the UMD globals the page loads from a CDN.
// The page calls the React 18 root API off the global, which the legacy
// @types/react-dom UMD namespace does not declare.
import { Root } from 'react-dom/client';

declare global {
  namespace ReactDOM {
    function createRoot(container: Element | DocumentFragment): Root;
  }
}
