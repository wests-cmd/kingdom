import React, { useState, useEffect } from "react";
import { fetchSkills, fetchLearningActivity, promoteProposal, triggerRollback } from "../api";

export default function Learning() {
  const [activity, setActivity] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadActivity();
  }, []);

  const loadActivity = async () => {
    try {
      const data = await fetchLearningActivity();
      setActivity(data);
    } catch (err) {
      console.error("Failed loading learning activity", err);
    } finally {
      setLoading(false);
    }
  };

  const handlePromote = async (proposalId, experimentId) => {
    try {
      await promoteProposal(proposalId, experimentId);
      loadActivity();
    } catch (err) {
      alert("Promotion failed: " + err.message);
    }
  };

  const handleRollback = async (skillId, fromVersion, toVersion) => {
    try {
      await triggerRollback(skillId, fromVersion, toVersion, "User requested rollback");
      loadActivity();
    } catch (err) {
      alert("Rollback failed: " + err.message);
    }
  };

  if (loading) return <div className="p-6 text-gray-400">Loading Learning Center...</div>;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <header className="border-b border-neutral-800 pb-4">
        <h1 className="text-2xl font-bold text-white tracking-wide">LEARNING CENTER</h1>
        <p className="text-sm text-neutral-400">Continuous Improvement, Evidence Collection & Autonomous Optimization Policy</p>
      </header>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-neutral-900 border border-neutral-800 p-4 rounded-lg">
          <div className="text-xs font-semibold text-neutral-500 uppercase">Proposals Active</div>
          <div className="text-2xl font-bold text-white mt-1">{activity?.proposals?.length || 0}</div>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 p-4 rounded-lg">
          <div className="text-xs font-semibold text-neutral-500 uppercase">Experiments Running</div>
          <div className="text-2xl font-bold text-emerald-400 mt-1">{activity?.experiments?.length || 0}</div>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 p-4 rounded-lg">
          <div className="text-xs font-semibold text-neutral-500 uppercase">Promotions</div>
          <div className="text-2xl font-bold text-blue-400 mt-1">{activity?.promotions?.length || 0}</div>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 p-4 rounded-lg">
          <div className="text-xs font-semibold text-neutral-500 uppercase">Rollbacks Triggered</div>
          <div className="text-2xl font-bold text-rose-500 mt-1">{activity?.rollbacks?.length || 0}</div>
        </div>
      </div>

      {/* Improvement Proposals List */}
      <section className="bg-neutral-900 border border-neutral-800 rounded-lg p-5 space-y-4">
        <h2 className="text-lg font-semibold text-white">Improvement Proposals & Before/After Evidence</h2>
        {(!activity?.proposals || activity.proposals.length === 0) ? (
          <div className="text-sm text-neutral-500 italic">No active improvement proposals recorded.</div>
        ) : (
          <div className="space-y-3">
            {activity.proposals.map((prop) => {
              const exp = activity?.experiments?.find(e => e.proposal_id === prop.id);
              return (
                <div key={prop.id} className="bg-neutral-950 border border-neutral-800 p-4 rounded text-sm space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-white">{prop.skill_id} ({prop.current_version} &rarr; {prop.proposed_version})</span>
                    <span className="px-2 py-0.5 rounded text-xs bg-amber-950 text-amber-400 border border-amber-800/50">{prop.status}</span>
                  </div>
                  <div className="text-neutral-400">
                    <div><strong>What was wrong:</strong> {prop.what_was_wrong}</div>
                    <div><strong>What Kingdom learned:</strong> {prop.what_kingdom_learned}</div>
                    <div><strong>Proposed Change:</strong> {prop.proposed_change}</div>
                  </div>
                  <div className="flex justify-between items-center pt-2 border-t border-neutral-900">
                    <div className="flex items-center space-x-4 text-xs text-neutral-500">
                      <span>Sample Count: {prop.sample_size}</span>
                      <span>Confidence: {(prop.confidence * 100).toFixed(0)}%</span>
                      <span>Risk: {prop.regression_risk}</span>
                    </div>
                    {exp && exp.status === "PASSED" && prop.status !== "PROMOTED" && (
                      <button
                        onClick={() => handlePromote(prop.id, exp.id)}
                        className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold"
                      >
                        PROMOTE IMPROVEMENT
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Promoted Improvements & Rollback Controls */}
      {activity?.promotions && activity.promotions.length > 0 && (
        <section className="bg-neutral-900 border border-neutral-800 rounded-lg p-5 space-y-4">
          <h2 className="text-lg font-semibold text-white">Promoted Improvements</h2>
          <div className="space-y-2">
            {activity.promotions.map((promo) => (
              <div key={promo.id} className="flex justify-between items-center bg-neutral-950 border border-neutral-800 p-3 rounded text-sm">
                <div>
                  <span className="font-bold text-white">{promo.skill_id}</span>
                  <span className="text-xs text-neutral-400 ml-2">Promoted to v{promo.promoted_version} by {promo.promoter}</span>
                </div>
                <button
                  onClick={() => handleRollback(promo.skill_id, promo.promoted_version, promo.old_version)}
                  className="px-2 py-1 bg-rose-900/60 border border-rose-700/50 text-rose-300 hover:bg-rose-800 rounded text-xs"
                >
                  ROLLBACK
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
