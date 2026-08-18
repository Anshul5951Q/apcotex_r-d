import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { Clock, ExternalLink } from 'lucide-react';
import * as api from '../../services/researchApi';
import { useRecipe } from '../../contexts/RecipeContext';

export function RecipeHistory() {
  const [cycles, setCycles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { setCycleId } = useRecipe();

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getRecipeCycles();
        setCycles(data);
      } catch (err) {
        console.error("Failed to load recipe history:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleOpenCycle = (id: string) => {
    setCycleId(id);
    navigate('/recipe-simulator');
  };

  if (loading) {
    return (
      <div style={{ padding: 24 }}>
        <h2>Recipe History</h2>
        <p>Loading past simulation sessions...</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <Clock size={28} color="#1F5FA8" />
        <h2 style={{ margin: 0, color: '#1F2937' }}>Recipe Simulation History</h2>
      </div>

      {cycles.length === 0 ? (
        <div style={{ background: 'white', padding: 32, borderRadius: 8, border: '1px solid #E5E7EB', textAlign: 'center' }}>
          <p style={{ color: '#6B7280' }}>No recipe simulations found.</p>
          <button
            onClick={() => navigate('/literature-review')}
            style={{
              marginTop: 16,
              background: '#1FB7B5',
              color: 'white',
              border: 'none',
              padding: '8px 16px',
              borderRadius: 6,
              cursor: 'pointer',
              fontWeight: 600
            }}
          >
            Start a new Research Run
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {cycles.map((cycle) => (
            <div
              key={cycle.id}
              style={{
                background: 'white',
                border: '1px solid #E5E7EB',
                borderRadius: 8,
                padding: 20,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                  <span style={{ fontWeight: 600, fontSize: '1.125rem', color: '#1F5FA8' }}>
                    {cycle.compound_name}
                  </span>
                  <span
                    style={{
                      background: '#F3F4F6',
                      padding: '2px 8px',
                      borderRadius: 12,
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      color: '#4B5563'
                    }}
                  >
                    {cycle.status}
                  </span>
                </div>
                <div style={{ color: '#6B7280', fontSize: '0.875rem' }}>
                  Started: {new Date(cycle.created_at).toLocaleDateString()}
                  {' • '}
                  {cycle.candidates?.length || 0} Candidates Generated
                  {cycle.trials?.length > 0 && ` • Trial Completed`}
                </div>
              </div>
              <button
                onClick={() => handleOpenCycle(cycle.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  background: 'white',
                  border: '1px solid #E5E7EB',
                  padding: '8px 16px',
                  borderRadius: 6,
                  color: '#374151',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Resume Session <ExternalLink size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
