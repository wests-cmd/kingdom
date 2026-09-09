import React, { useState, useEffect } from 'react';

export default function Integrations() {
  const [integrations, setIntegrations] = useState([
    {
      id: 'org.kingdom.github',
      name: 'GitHub Integration',
      version: '1.0.0',
      publisher: 'Kingdom Core',
      health: 'HEALTHY',
      risk: 'MEDIUM',
      capabilities: ['github.read', 'github.write'],
      permissions: ['repo:read', 'issue:create'],
      connected: true
    }
  ]);

  return (
    <div className="p-6 space-y-6 bg-[#0d0d0d] text-gray-200 min-h-screen">
      <div className="flex justify-between items-center border-b border-gray-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Integrations & Provider Ecosystem</h1>
          <p className="text-sm text-gray-400">Manage external provider connections, permissions, and credential boundaries.</p>
        </div>
        <button className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded font-medium text-sm transition-colors">
          + Connect Integration
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {integrations.map((item) => (
          <div key={item.id} className="bg-gray-900 border border-gray-800 rounded-lg p-5 space-y-4">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-lg font-semibold text-white">{item.name}</h3>
                <p className="text-xs text-gray-500">{item.id} • v{item.version}</p>
              </div>
              <span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${
                item.health === 'HEALTHY' ? 'bg-green-900/50 text-green-400 border border-green-800' : 'bg-red-900/50 text-red-400 border border-red-800'
              }`}>
                {item.health}
              </span>
            </div>

            <div className="space-y-2 text-sm text-gray-300">
              <div className="flex justify-between">
                <span className="text-gray-500">Publisher:</span>
                <span>{item.publisher}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Risk Level:</span>
                <span className="font-semibold text-yellow-400">{item.risk}</span>
              </div>
              <div>
                <span className="text-gray-500 text-xs block mb-1">Capabilities:</span>
                <div className="flex flex-wrap gap-1">
                  {item.capabilities.map((cap) => (
                    <span key={cap} className="px-2 py-0.5 bg-gray-800 text-xs text-gray-300 rounded">
                      {cap}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-gray-800 flex justify-between items-center">
              <span className="text-xs text-gray-500">Credential Broker: Isolated Handle Active</span>
              <button className="px-3 py-1.5 text-xs bg-red-900/30 text-red-400 hover:bg-red-900/60 border border-red-800 rounded transition-colors">
                Revoke
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
