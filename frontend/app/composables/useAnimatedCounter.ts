export function useAnimatedCounter(
  targetValue: number,
  duration: number = 800,
  easing: (t: number) => number = easeOutExpo
) {
  const displayValue = ref(0);
  const isAnimating = ref(false);

  function easeOutExpo(t: number): number {
    return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
  }

  function animate() {
    const startTime = performance.now();
    const startValue = displayValue.value;
    const diff = targetValue - startValue;

    if (diff === 0) return;

    isAnimating.value = true;

    function step(currentTime: number) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easedProgress = easing(progress);

      displayValue.value = Math.round(startValue + diff * easedProgress);

      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        displayValue.value = targetValue;
        isAnimating.value = false;
      }
    }

    requestAnimationFrame(step);
  }

  // Animate when target changes
  watch(() => targetValue, () => {
    animate();
  }, { immediate: true });

  return {
    displayValue,
    isAnimating,
    animate,
  };
}
