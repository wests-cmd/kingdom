import React, { useState, useEffect } from 'react';
import api from '../api';

export default function AdapterDiscovery() {
  const [adaptersData, setAdaptersData] = useState({ tools: [], models: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    api.get('/integrations/adapters')
      .then(res => {
        if (mounted) {
          setAdaptersData(res.data || { tools: [], models: [] });
          setLoading(false);
        }
      })
      .catch(err => {
        if (mounted) {
          // If unauthenticated or failing, preserve offline/graceful state
          setError(err.message || 'Unable to load adapters');
          setLoading(false);
        }
      });
    return () => { mounted = false; };
  }, []);

  return (
    <div className="space-y-6">
      <div className="border-b border-gray-800 pb-3">
        <h2 className="text-xl font-semibold text-white">External Coding Adapters & Model Readiness</h2>
        <p className="text-xs text-gray-400">
          Discovers installed apps and models without extracting browser cookies or account credentials.
        </p>
      </div>

      {loading && <p className="text-xs text-gray-500">Scanning installed coding tools and model profiles...</p>}

      {error && (
        <div className="p-3 bg-red-950/40 border border-red-800 rounded text-xs text-red-300">
          Note: {error}. Showing standard protocol configuration.
        </div>
      )}

      <div>
        <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3">
          Coding Application Adapters (ACP & Wrappers)
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(adaptersData.tools || []).map(tool => (
            <div key={tool.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
              <div className="flex justify-between items-start">
                <div>
                  <h4 className="text-base font-medium text-white">{tool.name}</h4>
                  <span className="text-xs text-gray-500 font-mono">{tool.executable}</span>
                </div>
                <span className={`px-2 py-0.5 text-xs font-semibold rounded ${
                  tool.installed
                    ? 'bg-green-900/40 text-green-400 border border-green-800'
                    : 'bg-yellow-900/40 text-yellow-400 border border-yellow-800'
                }`}>
                  {tool.installed ? 'Ready' : 'Not Installed'}
                </span>
              </div>

              <div className="text-xs space-y-1 text-gray-300">
                <div className="flex justify-between">
                  <span className="text-gray-500">Protocol:</span>
                  <span className="font-mono">{tool.protocol.toUpperCase()} {tool.supports_acp ? '(ACP Native)' : '(CLI)'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Protocol Version:</span>
                  <span>{tool.protocol_version}</span>
                </div>
              </div>

              <div>
                <span className="text-gray-500 text-xs block mb-1">Capabilities:</span>
                <div className="flex flex-wrap gap-1">
                  {(tool.capabilities || []).map(cap => (
                    <span key={cap} className="px-1.5 py-0.5 bg-gray-800 text-[11px] text-gray-300 rounded font-mono">
                      {cap}
                    </span>
                  ))}
                </div>
              </div>

              {tool.beginner_setup_guide && (
                <div className="pt-2 border-t border-gray-800 text-[11px] text-gray-400 space-y-1">
                  <div><strong className="text-gray-300">Install:</strong> {tool.beginner_setup_guide.install_hint}</div>
                  <div><strong className="text-gray-300">Sign-in:</strong> {tool.beginner_setup_guide.signin_hint}</div>
                </div>
              )}

              {tool.unavailable_reasons && tool.unavailable_reasons.length > 0 && (
                <div className="text-[11px] text-yellow-500/90 bg-yellow-950/20 p-2 rounded border border-yellow-900/50">
                  {tool.unavailable_reasons.join(', ')}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="pt-4">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3">
          Supported Model Profiles & Capability Readiness
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {(adaptersData.models || []).map(model => (
            <div key={model.id} className="bg-gray-900 border border-gray-800 rounded-lg p-3 space-y-2">
              <div className="flex justify-between items-start">
                <h4 className="text-sm font-medium text-white">{model.name}</h4>
                <span className={`px-1.5 py-0.5 text-[10px] font-semibold rounded ${
                  model.is_local ? 'bg-blue-900/40 text-blue-300 border border-blue-800' : 'bg-purple-900/40 text-purple-300 border border-purple-800'
                }`}>
                  {model.is_local ? 'Local' : 'Cloud'}
                </span>
              </div>
              <p className="text-[11px] text-gray-400">{model.notes}</p>
              <div className="text-[11px] text-gray-500 space-y-1">
                <div>Context: {model.context_window?.toLocaleString()} tokens</div>
                <div>Tools: {model.supports_tools ? 'Supported' : 'Unavailable'}</div>
                <div>Vision: {model.supports_vision ? 'Supported' : 'Unavailable'}</div>
              </div>
              {model.unavailable_reasons && model.unavailable_reasons.length > 0 && (
                <div className="text-[10px] text-yellow-500 bg-yellow-950/20 p-1.5 rounded">
                  {model.unavailable_reasons.join(', ')}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
