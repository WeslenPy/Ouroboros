import { useTheme } from '../provider/theme';
import { Sun, Moon } from 'lucide-react';
import { Button } from '@/ui/button';

export const ThemeToggleButton = () => {
  const { theme, toggle } = useTheme();
  return (
    <Button
      variant={"ghost"}
      onClick={toggle}
      aria-label="Alternar tema"
    >
      {theme === 'dark' ? (
        <>
          <Sun  />
        </>
      ) : (
        <>
          <Moon  />
        </>
      )}
    </Button>
  );
};
