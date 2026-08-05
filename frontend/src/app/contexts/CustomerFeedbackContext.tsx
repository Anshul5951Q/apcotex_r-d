import { createContext, useContext, useState, ReactNode } from 'react';
import type { SpecRowTemplate } from '../components/apcotex/recipeSimulatorDemoData';

interface CustomerFeedbackContextType {
  customerFeedbackProperties: SpecRowTemplate[];
  addCustomerFeedbackProperty: (property: Omit<SpecRowTemplate, 'id'>) => void;
  updateCustomerFeedbackProperty: (id: string, updates: Partial<SpecRowTemplate>) => void;
  deleteCustomerFeedbackProperty: (id: string) => void;
  getCustomerFeedbackPropertyById: (id: string) => SpecRowTemplate | undefined;
}

const CustomerFeedbackContext = createContext<CustomerFeedbackContextType | undefined>(undefined);

export function CustomerFeedbackProvider({ children, initialProperties }: { 
  children: ReactNode;
  initialProperties: SpecRowTemplate[];
}) {
  const [customerFeedbackProperties, setCustomerFeedbackProperties] = useState<SpecRowTemplate[]>(initialProperties);

  const addCustomerFeedbackProperty = (property: Omit<SpecRowTemplate, 'id'>) => {
    const newProperty: SpecRowTemplate = {
      ...property,
      id: `cf-prop-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    };
    setCustomerFeedbackProperties((prev) => [...prev, newProperty]);
  };

  const updateCustomerFeedbackProperty = (id: string, updates: Partial<SpecRowTemplate>) => {
    setCustomerFeedbackProperties((prev) =>
      prev.map((prop) => (prop.id === id ? { ...prop, ...updates } : prop))
    );
  };

  const deleteCustomerFeedbackProperty = (id: string) => {
    setCustomerFeedbackProperties((prev) => prev.filter((prop) => prop.id !== id));
  };

  const getCustomerFeedbackPropertyById = (id: string) => {
    return customerFeedbackProperties.find((prop) => prop.id === id);
  };

  return (
    <CustomerFeedbackContext.Provider
      value={{
        customerFeedbackProperties,
        addCustomerFeedbackProperty,
        updateCustomerFeedbackProperty,
        deleteCustomerFeedbackProperty,
        getCustomerFeedbackPropertyById,
      }}
    >
      {children}
    </CustomerFeedbackContext.Provider>
  );
}

export function useCustomerFeedbackProperties() {
  const context = useContext(CustomerFeedbackContext);
  if (context === undefined) {
    throw new Error('useCustomerFeedbackProperties must be used within a CustomerFeedbackProvider');
  }
  return context;
}