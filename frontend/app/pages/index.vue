<template>
  <div class="min-h-screen bg-surface dark:bg-surface-dark text-text dark:text-text-dark transition-colors duration-300">
    <!-- Header -->
    <header class="fixed top-0 left-0 right-0 z-50 bg-surface/80 dark:bg-surface-dark/80 backdrop-blur-md border-b border-border dark:border-border-dark">
      <div class="mx-auto px-6 h-14 flex items-center justify-between"
        :class="pageState === 'completed' ? '' : 'max-w-5xl'"
      >
        <button class="flex items-center gap-2.5" @click="reset">
          <img src="~/assets/svg/logo.svg" alt="ValiRef" class="h-10" />
        </button>
        <div class="flex items-center gap-3">
          <!-- Theme toggle -->
          <button
            class="w-8 h-8 flex items-center justify-center rounded-lg text-text-secondary dark:text-text-dark-secondary hover:bg-surface-secondary dark:hover:bg-surface-dark-secondary"
            @click="toggleTheme"
            :aria-label="isDark ? '切换到浅色模式' : '切换到深色模式'"
          >
            <span v-if="isDark" class="i-lucide-sun w-5 h-5" />
            <span v-else class="i-lucide-moon w-5 h-5" />
          </button>
          <!-- GitHub Star button -->
          <a
            href="https://github.com/Gianthard-cyh/ValiRef"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-lg bg-surface dark:bg-surface-dark border border-border dark:border-border-dark hover:border-border-strong dark:hover:border-border-dark-strong transition-all duration-200"
          >
            <span class="i-lucide-github w-4 h-4 text-text dark:text-text-dark" />
            <span class="text-caption text-text-secondary dark:text-text-dark-secondary">Star</span>
            <span v-if="starCount" class="text-caption font-medium text-text dark:text-text-dark tabular-nums">{{ starCount }}</span>
          </a>
          <TaskHistoryDropdown />
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="pt-14">
      <!-- Upload State - with diagonal pattern background -->
      <div v-if="pageState === 'idle' || pageState === 'error'" class="relative">
        <!-- Diagonal pattern background - light mode -->
        <div class="absolute inset-0 pointer-events-none dark:hidden bg-surface-tertiary"
             style="background-image: repeating-linear-gradient(315deg, var(--pattern-fg, #d4d4d4) 0, var(--pattern-fg, #d4d4d4) 1px, transparent 0, transparent 50%); background-size: 30px 30px;" />
        <!-- Diagonal pattern background - dark mode -->
        <div class="absolute inset-0 pointer-events-none hidden dark:block bg-surface-dark-tertiary"
             style="background-image: repeating-linear-gradient(315deg, var(--pattern-fg-dark, #404040) 0, var(--pattern-fg-dark, #404040) 1px, transparent 0, transparent 50%); background-size: 30px 30px;" />

        <UploadView />
      </div>

      <!-- Processing State -->
      <ProcessingView v-if="pageState === 'processing'" />

      <!-- Results State -->
      <ResultView
        v-if="pageState === 'completed' && currentResult"
        :result="currentResult"
        :pdf-url="pdfUrl"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
const taskStore = useTaskStore();
const colorMode = useColorMode({
  attribute: 'class',
  modes: {
    dark: 'dark',
  },
});

const { pageState, currentResult, currentPDFFile } = storeToRefs(taskStore);
const { reset } = taskStore;

const pdfUrl = ref<string>('');
const starCount = ref<number>(0);

const isDark = computed(() => colorMode.value === 'dark');

async function fetchStarCount() {
  try {
    const response = await fetch('https://api.github.com/repos/Gianthard-cyh/ValiRef');
    if (response.ok) {
      const data = await response.json();
      starCount.value = data.stargazers_count;
    }
  } catch (e) {
    // 静默失败，不显示数量
  }
}

onMounted(() => {
  fetchStarCount();
});

function toggleTheme() {
  colorMode.value = colorMode.value === 'dark' ? 'light' : 'dark';
}

watch(currentResult, (result) => {
  if (result?.filename && currentPDFFile.value) {
    pdfUrl.value = URL.createObjectURL(currentPDFFile.value);
  }
});

onUnmounted(() => {
  if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value);
});
</script>
