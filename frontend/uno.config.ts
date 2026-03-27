import { defineConfig, presetUno, presetAttributify, presetIcons } from 'unocss';
import { icons as lucideIcons } from '@iconify-json/lucide';

export default defineConfig({
  presets: [
    presetUno(),
    presetAttributify(),
    presetIcons({
      scale: 1.2,
      extraProperties: {
        'display': 'inline-block',
        'vertical-align': 'middle',
      },
      collections: {
        lucide: lucideIcons,
      },
    }),
  ],
  theme: {
    colors: {
      // Semantic type colors (work in both modes)
      'type-real': {
        DEFAULT: '#10b981',
        dark: '#34d399',
      },
      'type-fabrication': {
        DEFAULT: '#f43f5e',
        dark: '#fb7185',
      },
      'type-attribution': {
        DEFAULT: '#f59e0b',
        dark: '#fbbf24',
      },
      'type-irrelevance': {
        DEFAULT: '#3b82f6',
        dark: '#60a5fa',
      },
      'type-counter': {
        DEFAULT: '#8b5cf6',
        dark: '#a78bfa',
      },
      // Surface colors
      'surface': {
        DEFAULT: '#ffffff',
        secondary: '#fafafa',
        tertiary: '#f5f5f5',
        dark: '#0a0a0a',
        'dark-secondary': '#171717',
        'dark-tertiary': '#262626',
      },
      // Text colors
      'text': {
        DEFAULT: '#171717',
        secondary: '#525252',
        tertiary: '#737373',
        muted: '#a3a3a3',
        dark: '#fafafa',
        'dark-secondary': '#e5e5e5',
        'dark-tertiary': '#a3a3a3',
      },
      // Border colors
      'border': {
        DEFAULT: '#e5e5e5',
        strong: '#d4d4d4',
        subtle: '#f5f5f5',
        dark: '#262626',
        'dark-strong': '#404040',
        'dark-subtle': '#171717',
      },
    },
    fontFamily: {
      sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      display: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
    },
  },
  shortcuts: {
    // Cards
    'line-card': 'bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-6 transition-all duration-200',
    'line-card-hover': 'hover:border-border-strong dark:hover:border-border-dark-strong hover:shadow-sm',

    // Buttons
    'line-btn': 'px-5 py-2.5 bg-text text-surface dark:bg-text-dark dark:text-surface-dark rounded-lg font-medium text-sm transition-all duration-200 hover:opacity-90 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-text/20 dark:focus:ring-text-dark/20 disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100',
    'line-btn-outline': 'px-5 py-2.5 border border-border-strong dark:border-border-dark-strong rounded-lg font-medium text-sm text-text dark:text-text-dark transition-all duration-200 hover:bg-surface-secondary dark:hover:bg-surface-dark-secondary hover:border-text dark:hover:border-text-dark focus:outline-none focus:ring-2 focus:ring-text/10 dark:focus:ring-text-dark/10',
    'line-btn-ghost': 'px-5 py-2.5 rounded-lg font-medium text-sm text-text-secondary dark:text-text-dark-secondary transition-all duration-200 hover:bg-surface-secondary dark:hover:bg-surface-dark-secondary hover:text-text dark:hover:text-text-dark focus:outline-none focus:ring-2 focus:ring-text/10 dark:focus:ring-text-dark/10',
    'line-btn-disabled': 'px-5 py-2.5 bg-surface-tertiary dark:bg-surface-dark-tertiary rounded-lg font-medium text-sm text-text-muted dark:text-text-dark-tertiary cursor-not-allowed',

    // Inputs
    'line-input': 'w-full px-4 py-3 bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg text-text dark:text-text-dark placeholder:text-text-muted dark:placeholder:text-text-dark-tertiary transition-all duration-200 focus:border-border-strong dark:focus:border-border-dark-strong focus:outline-none focus:ring-2 focus:ring-text/5 dark:focus:ring-text-dark/5',

    // Dividers
    'line-divider': 'h-px bg-border dark:bg-border-dark w-full',

    // Focus rings
    'focus-ring': 'focus:outline-none focus:ring-2 focus:ring-text/20 dark:focus:ring-text-dark/20 focus:ring-offset-2 focus:ring-offset-surface dark:focus:ring-offset-surface-dark',
    'focus-ring-subtle': 'focus:outline-none focus:ring-2 focus:ring-text/10 dark:focus:ring-text-dark/10',

    // Animation utilities
    'animate-enter': 'opacity-0 animate-fade-in-up',
    'animate-enter-delay-1': 'opacity-0 animate-fade-in-up stagger-1',
    'animate-enter-delay-2': 'opacity-0 animate-fade-in-up stagger-2',
    'animate-enter-delay-3': 'opacity-0 animate-fade-in-up stagger-3',
    'animate-enter-delay-4': 'opacity-0 animate-fade-in-up stagger-4',
    'animate-enter-delay-5': 'opacity-0 animate-fade-in-up stagger-5',
    'animate-enter-delay-6': 'opacity-0 animate-fade-in-up stagger-6',
  },
  rules: [
    // Fluid typography
    [
      /^text-fluid-(xs|sm|base|lg|xl|2xl|3xl)$/,
      ([, size]) => {
        const sizes: Record<string, string> = {
          xs: 'clamp(0.75rem, 0.7rem + 0.25vw, 0.875rem)',
          sm: 'clamp(0.875rem, 0.8rem + 0.35vw, 1rem)',
          base: 'clamp(1rem, 0.9rem + 0.5vw, 1.125rem)',
          lg: 'clamp(1.125rem, 1rem + 0.6vw, 1.25rem)',
          xl: 'clamp(1.25rem, 1.1rem + 0.75vw, 1.5rem)',
          '2xl': 'clamp(1.5rem, 1.3rem + 1vw, 2rem)',
          '3xl': 'clamp(1.875rem, 1.5rem + 1.5vw, 2.5rem)',
        };
        return { 'font-size': sizes[size] };
      },
    ],
  ],
});
