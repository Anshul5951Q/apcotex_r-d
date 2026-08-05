import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";

export type RunStatus = 
  | "PENDING"
  | "SEARCHING"
  | "FILTERING"
  | "EXTRACTING"
  | "GENERATING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export interface PatentResearchState {
  researchRunId: string | null;
  status: RunStatus | null;
  reportHtml: string | null;
  reportMarkdown: string | null;
  recipeData: any | null; // Extracted JSON properties for the simulator
  error: string | null;
  compoundName: string | null;
  createdDate: string | null;
}

interface PatentResearchContextType {
  state: PatentResearchState;
  setState: (newState: Partial<PatentResearchState>) => void;
  clearState: () => void;
}

const defaultState: PatentResearchState = {
  researchRunId: null,
  status: null,
  reportHtml: null,
  reportMarkdown: null,
  recipeData: null,
  error: null,
  compoundName: null,
  createdDate: null,
};

const PatentResearchContext = createContext<
  PatentResearchContextType | undefined
>(undefined);

export function PatentResearchProvider({ children }: { children: ReactNode }) {
  const [state, setInternalState] = useState<PatentResearchState>(defaultState);

  const setState = useCallback((newState: Partial<PatentResearchState>) => {
    setInternalState((prev) => ({ ...prev, ...newState }));
  }, []);

  const clearState = useCallback(() => {
    setInternalState(defaultState);
  }, []);

  return (
    <PatentResearchContext.Provider
      value={{ state, setState, clearState }}
    >
      {children}
    </PatentResearchContext.Provider>
  );
}

export function usePatentResearch() {
  const context = useContext(PatentResearchContext);
  if (context === undefined) {
    throw new Error(
      "usePatentResearch must be used within a PatentResearchProvider",
    );
  }
  return context;
}
