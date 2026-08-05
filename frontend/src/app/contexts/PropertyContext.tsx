import { createContext, useContext, useState, ReactNode } from 'react';
import type { SpecRowTemplate } from '../components/apcotex/recipeSimulatorDemoData';

interface PropertyContextType {
  properties: SpecRowTemplate[];
  addProperty: (property: Omit<SpecRowTemplate, 'id'>) => void;
  updateProperty: (id: string, updates: Partial<SpecRowTemplate>) => void;
  deleteProperty: (id: string) => void;
  getPropertyById: (id: string) => SpecRowTemplate | undefined;
}

const PropertyContext = createContext<PropertyContextType | undefined>(undefined);

export function PropertyProvider({ children, initialProperties }: { 
  children: ReactNode;
  initialProperties: SpecRowTemplate[];
}) {
  const [properties, setProperties] = useState<SpecRowTemplate[]>(initialProperties);

  const addProperty = (property: Omit<SpecRowTemplate, 'id'>) => {
    const newProperty: SpecRowTemplate = {
      ...property,
      id: `prop-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    };
    setProperties((prev) => [...prev, newProperty]);
  };

  const updateProperty = (id: string, updates: Partial<SpecRowTemplate>) => {
    setProperties((prev) =>
      prev.map((prop) => (prop.id === id ? { ...prop, ...updates } : prop))
    );
  };

  const deleteProperty = (id: string) => {
    setProperties((prev) => prev.filter((prop) => prop.id !== id));
  };

  const getPropertyById = (id: string) => {
    return properties.find((prop) => prop.id === id);
  };

  return (
    <PropertyContext.Provider
      value={{
        properties,
        addProperty,
        updateProperty,
        deleteProperty,
        getPropertyById,
      }}
    >
      {children}
    </PropertyContext.Provider>
  );
}

export function useProperties() {
  const context = useContext(PropertyContext);
  if (context === undefined) {
    throw new Error('useProperties must be used within a PropertyProvider');
  }
  return context;
}