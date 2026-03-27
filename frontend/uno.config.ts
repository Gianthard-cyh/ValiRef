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
      'type-real': '#10b981',
      'type-fabrication': '#f43f5e',
      'type-attribution': '#f59e0b',
      'type-irrelevance': '#3b82f6',
      'type-counter': '#8b5cf6',
    },
  },
  shortcuts: {
    'line-card': 'bg-white border border-gray-200 rounded p-6',
    'line-btn': 'px-6 py-3 border border-gray-900 rounded font-medium hover:bg-gray-900 hover:text-white transition-all duration-200 cursor-pointer',
    'line-btn-outline': 'px-6 py-3 border border-gray-200 rounded text-gray-700 hover:border-gray-400 hover:text-gray-900 transition-all duration-200 cursor-pointer',
    'line-btn-disabled': 'px-6 py-3 border border-gray-300 rounded text-gray-400 cursor-not-allowed',
    'line-input': 'w-full px-4 py-3 border border-gray-200 rounded bg-white focus:border-gray-400 focus:outline-none focus:ring-1 focus:ring-gray-400 transition-all duration-200',
    'line-divider': 'h-px bg-gray-200 w-full',
  },
});
