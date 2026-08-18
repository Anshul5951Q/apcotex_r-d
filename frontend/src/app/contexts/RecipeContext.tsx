import React, { createContext, useContext, useState, useEffect } from 'react';
import * as api from '../services/researchApi';

interface RecipeContextType {
  cycleId: string | null;
  cycle: any | null;
  candidates: any[];
  selectedCandidate: any | null;
  trial: any | null;
  optimizedCandidates: any[];
  selectedOptimized: any | null;
  
  loading: boolean;
  generating: boolean;
  optimizing: boolean;
  error: string | null;

  setCycleId: (id: string | null) => void;
  loadCycle: (id: string) => Promise<void>;
  createCycle: (payload: any) => Promise<string>;
  updateCycle: (payload: any) => Promise<void>;
  generateRecipes: () => Promise<void>;
  selectCandidate: (candidateId: string) => Promise<void>;
  createTrial: (payload: any) => Promise<void>;
  updateTrial: (payload: any) => Promise<void>;
  generateOptimization: () => Promise<void>;
  selectOptimized: (optimizedId: string) => Promise<void>;
  resetContext: () => void;
}

const RecipeContext = createContext<RecipeContextType | undefined>(undefined);

export function RecipeProvider({ children }: { children: React.ReactNode }) {
  const [cycleId, setCycleIdState] = useState<string | null>(() => {
    return localStorage.getItem('activeRecipeCycleId');
  });
  const [cycle, setCycle] = useState<any | null>(null);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<any | null>(null);
  const [trial, setTrial] = useState<any | null>(null);
  const [optimizedCandidates, setOptimizedCandidates] = useState<any[]>([]);
  const [selectedOptimized, setSelectedOptimized] = useState<any | null>(null);

  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setCycleId = (id: string | null) => {
    setCycleIdState(id);
    if (id) {
      localStorage.setItem('activeRecipeCycleId', id);
    } else {
      localStorage.removeItem('activeRecipeCycleId');
    }
  };

  const resetContext = () => {
    setCycleId(null);
    setCycle(null);
    setCandidates([]);
    setSelectedCandidate(null);
    setTrial(null);
    setOptimizedCandidates([]);
    setSelectedOptimized(null);
    setError(null);
  };

  const loadCycle = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getRecipeCycle(id);
      setCycle(data);
      
      const cands = data.candidates || [];
      setCandidates(cands);
      
      const selected = cands.find((c: any) => c.is_selected);
      setSelectedCandidate(selected || null);

      const trials = data.trials || [];
      if (trials.length > 0) {
        // Just take the first/latest trial for simplicity
        const activeTrial = trials[0];
        setTrial(activeTrial);
        const opts = activeTrial.optimized_candidates || [];
        setOptimizedCandidates(opts);
        const selOpt = opts.find((o: any) => o.is_selected);
        setSelectedOptimized(selOpt || null);
      } else {
        setTrial(null);
        setOptimizedCandidates([]);
        setSelectedOptimized(null);
      }
      
      setCycleId(id);
    } catch (err: any) {
      setError(err.message || "Failed to load recipe cycle");
      if (err.message.includes("404")) resetContext();
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (cycleId && !cycle && !loading) {
      loadCycle(cycleId);
    }
  }, [cycleId]);

  const createCycle = async (payload: any) => {
    setLoading(true);
    setError(null);
    try {
      const newCycle = await api.createRecipeCycle(payload);
      setCycle(newCycle);
      setCycleId(newCycle.id);
      return newCycle.id;
    } catch (err: any) {
      setError(err.message || "Failed to create recipe cycle");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const updateCycle = async (payload: any) => {
    if (!cycleId) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await api.updateRecipeCycle(cycleId, payload);
      setCycle(updated);
    } catch (err: any) {
      setError(err.message || "Failed to update recipe cycle");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const generateRecipes = async () => {
    if (!cycleId) return;
    setGenerating(true);
    setError(null);
    try {
      const cands = await api.generateRecipes(cycleId);
      setCandidates(cands);
      // reload cycle state to get latest status
      const updated = await api.getRecipeCycle(cycleId);
      setCycle(updated);
    } catch (err: any) {
      setError(err.message || "Failed to generate recipes");
      throw err;
    } finally {
      setGenerating(false);
    }
  };

  const selectCandidate = async (candidateId: string) => {
    if (!cycleId) return;
    setLoading(true);
    setError(null);
    try {
      const updatedCycle = await api.selectCandidate(cycleId, candidateId);
      setCycle(updatedCycle);
      
      // update local candidate array
      const updatedCandidates = candidates.map(c => ({
        ...c,
        is_selected: c.id === candidateId
      }));
      setCandidates(updatedCandidates);
      
      const sel = updatedCandidates.find(c => c.id === candidateId);
      setSelectedCandidate(sel || null);
    } catch (err: any) {
      setError(err.message || "Failed to select candidate");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const createTrial = async (payload: any) => {
    if (!selectedCandidate) return;
    setLoading(true);
    setError(null);
    try {
      const newTrial = await api.createCustomerTrial({
        selected_candidate_id: selectedCandidate.id,
        ...payload
      });
      setTrial(newTrial);
      
      // Update cycle status locally
      if (cycle) {
        setCycle({...cycle, status: 'STEP3'});
      }
    } catch (err: any) {
      setError(err.message || "Failed to create trial");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const updateTrial = async (payload: any) => {
    if (!trial) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await api.updateCustomerTrial(trial.id, payload);
      setTrial(updated);
    } catch (err: any) {
      setError(err.message || "Failed to update trial");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const generateOptimization = async () => {
    if (!trial) return;
    setOptimizing(true);
    setError(null);
    try {
      const opts = await api.generateOptimization(trial.id);
      setOptimizedCandidates(opts);
      
      const updatedTrial = await api.updateCustomerTrial(trial.id, {}); // reload status essentially
      setTrial({...trial, status: 'COMPLETED'});
      
      if (cycle) {
        setCycle({...cycle, status: 'STEP4'});
      }
    } catch (err: any) {
      setError(err.message || "Failed to generate optimization");
      throw err;
    } finally {
      setOptimizing(false);
    }
  };

  const selectOptimized = async (optimizedId: string) => {
    if (!trial) return;
    setLoading(true);
    setError(null);
    try {
      const updatedTrial = await api.selectOptimized(trial.id, optimizedId);
      setTrial(updatedTrial);
      
      const updatedOpts = optimizedCandidates.map(o => ({
        ...o,
        is_selected: o.id === optimizedId
      }));
      setOptimizedCandidates(updatedOpts);
      
      const sel = updatedOpts.find(o => o.id === optimizedId);
      setSelectedOptimized(sel || null);
      
      if (cycle) {
        setCycle({...cycle, status: 'COMPLETED'});
      }
    } catch (err: any) {
      setError(err.message || "Failed to select optimized candidate");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const value: RecipeContextType = {
    cycleId,
    cycle,
    candidates,
    selectedCandidate,
    trial,
    optimizedCandidates,
    selectedOptimized,
    loading,
    generating,
    optimizing,
    error,
    setCycleId,
    loadCycle,
    createCycle,
    updateCycle,
    generateRecipes,
    selectCandidate,
    createTrial,
    updateTrial,
    generateOptimization,
    selectOptimized,
    resetContext,
  };

  return <RecipeContext.Provider value={value}>{children}</RecipeContext.Provider>;
}

export function useRecipe() {
  const context = useContext(RecipeContext);
  if (context === undefined) {
    throw new Error('useRecipe must be used within a RecipeProvider');
  }
  return context;
}
