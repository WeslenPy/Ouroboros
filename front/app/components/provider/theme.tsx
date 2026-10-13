import { createContext, useContext, useEffect, useState } from 'react';
import type  {ReactNode} from 'react';

type Theme = 'light' | 'dark';

interface ThemeContextValue {
  theme: Theme;
  toggle: () => void;
  setLight: () => void;
  setDark: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);
const STORAGE_KEY = 'theme-preference';

export const ThemeProvider = ({ children }: { children: ReactNode }) => {
  const [theme, setTheme] = useState<Theme>('light');

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY) as Theme | null;
    if (stored === 'dark' || stored === 'light') {
      setTheme(stored);
      applyClass(stored);
    } else {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      const initial: Theme = prefersDark ? 'dark' : 'light';
      setTheme(initial);
      applyClass(initial);
    }
  }, []);

  const applyClass = (t: Theme) => {
    if (t === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  };

  const setDark = () => {
    setTheme('dark');
    applyClass('dark');
    window.localStorage.setItem(STORAGE_KEY, 'dark');
  };

  const setLight = () => {
    setTheme('light');
    applyClass('light');
    window.localStorage.setItem(STORAGE_KEY, 'light');
  };

  const toggle = () => {
    theme === 'dark' ? setLight() : setDark();
  };

  return (
    <ThemeContext.Provider value={{ theme, toggle, setLight, setDark }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be inside ThemeProvider');
  return ctx;
};
