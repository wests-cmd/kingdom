import React, { useState, useEffect } from "react";
import { fetchSkills, fetchSkillMap, checkSkillReadiness } from "../api";

export default function Skills() {
  const [skills, setSkills] = useState([]);
  const [skillMap, setSkillMap] = useState(null);
  const [selectedSkill, setSelectedSkill] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const skillList = await fetchSkills();
      const mapData = await fetchSkillMap();
      setSkills(skillList || []);
      setSkillMap(mapData);
    } catch (err) {
      console.error("Failed loading skills", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = async (skill) => {
    setSelectedSkill(skill);
    try {
      const res = await checkSkillReadiness(skill.id);
      setReadiness(res);
    } catch (err) {
      console.error("Readiness check failed", err);
    }
  };

  if (loading) return <div className="p-6 text-gray-400">Loading AI Skill Platform...</div>;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <header className="border-b border-neutral-800 pb-4">
        <h1 className="text-2xl font-bold text-white tracking-wide">AI SKILL MAP & MANAGEMENT</h1>
        <p className="text-sm text-neutral-400">Typed & Versioned Skill Intelligence Lifecycle, Dependency Engine & Bundles</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3 lg:col-span-1">
          <h2 className="text-lg font-semibold text-white">Skill Catalog ({skills.length})</h2>
          <div className="space-y-2 overflow-y-auto max-h-[600px] pr-1">
            {skills.map((s) => (
              <div
                key={s.id}
                onClick={() => handleSelect(s)}
                className={`p-3 rounded border cursor-pointer transition ${
                  selectedSkill?.id === s.id
                    ? "bg-neutral-800 border-red-500 text-white"
                    : "bg-neutral-950 border-neutral-800 text-neutral-300 hover:border-neutral-700"
                }`}
              >
                <div className="flex justify-between items-center font-bold">
                  <span>{s.name}</span>
                  <span className="text-xs px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400">{s.version}</span>
                </div>
                <div className="text-xs text-neutral-500 mt-1">{s.description || "No description provided."}</div>
                <div className="flex justify-between items-center text-xs mt-2 text-neutral-400">
                  <span className="uppercase text-[10px] tracking-wider px-1 bg-neutral-900 border border-neutral-800 rounded">{s.state}</span>
                  <span>{s.department}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-5 space-y-6 lg:col-span-2">
          {selectedSkill ? (
            <>
              <div>
                <div className="flex justify-between items-start">
                  <div>
                    <h2 className="text-xl font-bold text-white">{selectedSkill.name}</h2>
                    <p className="text-xs text-neutral-400 mt-0.5">ID: {selectedSkill.id} | Version: {selectedSkill.version} | Trust: {selectedSkill.trust_level}</p>
                  </div>
                  <span className="px-2 py-1 rounded text-xs font-bold bg-neutral-800 border border-neutral-700 text-white uppercase">{selectedSkill.state}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm bg-neutral-950 border border-neutral-800 p-4 rounded">
                <div>
                  <span className="text-xs font-semibold text-neutral-500 uppercase block">Required Tools</span>
                  <span className="text-white">{selectedSkill.dependencies?.required_tools?.join(", ") || "None"}</span>
                </div>
                <div>
                  <span className="text-xs font-semibold text-neutral-500 uppercase block">Required Capabilities</span>
                  <span className="text-white">{selectedSkill.dependencies?.required_capabilities?.join(", ") || "None"}</span>
                </div>
                <div className="mt-2">
                  <span className="text-xs font-semibold text-neutral-500 uppercase block">Required Models</span>
                  <span className="text-white">{selectedSkill.dependencies?.required_models?.join(", ") || "None"}</span>
                </div>
                <div className="mt-2">
                  <span className="text-xs font-semibold text-neutral-500 uppercase block">Permissions</span>
                  <span className="text-white">{selectedSkill.permissions?.join(", ") || "None"}</span>
                </div>
              </div>

              <div className="border border-neutral-800 rounded p-4 bg-neutral-950 space-y-3">
                <h3 className="text-sm font-bold text-neutral-300 uppercase tracking-wider">"DO I HAVE EVERYTHING?" — READINESS REPORT</h3>
                {readiness ? (
                  <div>
                    <div className="flex items-center space-x-3">
                      <span className={`text-lg font-black ${readiness.status === "READY" ? "text-emerald-400" : "text-rose-500"}`}>
                        {readiness.status}
                      </span>
                    </div>
                    {readiness.blockers?.length > 0 && (
                      <ul className="mt-2 space-y-1 text-xs text-rose-400 list-disc list-inside">
                        {readiness.blockers.map((b, idx) => (
                          <li key={idx}>{b}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-neutral-500">Checking readiness engine...</div>
                )}
              </div>
            </>
          ) : (
            <div className="text-sm text-neutral-500 italic p-12 text-center">Select a skill from the catalog to view details, dependencies, and readiness status.</div>
          )}
        </div>
      </div>
    </div>
  );
}
