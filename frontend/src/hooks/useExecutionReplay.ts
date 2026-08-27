import { useState, useEffect, useRef, useCallback } from "react";

export type ReplaySpeed = 0.5 | 1 | 2 | 5;

export interface ReplayState {
  isReplaying: boolean;
  isPlaying: boolean;
  currentIndex: number;
  speed: ReplaySpeed;
  visibleEvents: Record<string, unknown>[];
  totalEvents: number;
  isFinished: boolean;
}

export function useExecutionReplay(actualEvents: Record<string, unknown>[]) {
  const [isReplaying, setIsReplaying] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [speed, setSpeed] = useState<ReplaySpeed>(1);

  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const totalEvents = actualEvents.length;
  const visibleEvents = isReplaying ? actualEvents.slice(0, currentIndex + 1) : actualEvents;
  const isFinished = isReplaying && totalEvents > 0 && currentIndex >= totalEvents - 1;

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const playNext = useCallback(() => {
    setCurrentIndex((prev) => {
      const nextIndex = prev + 1;
      if (nextIndex >= actualEvents.length - 1) {
        setIsPlaying(false);
        return actualEvents.length - 1;
      }
      return nextIndex;
    });
  }, [actualEvents.length]);

  useEffect(() => {
    if (!isPlaying || isFinished || actualEvents.length === 0) {
      clearTimer();
      return;
    }

    const currentEvent = actualEvents[currentIndex];
    const nextEvent = actualEvents[currentIndex + 1];

    if (!currentEvent || !nextEvent) {
      // Just clear the timer, playNext will handle the bounds
      clearTimer();
      return;
    }

    const currentTsStr = currentEvent.timestamp as string | undefined;
    const nextTsStr = nextEvent.timestamp as string | undefined;

    let delay = 150; // default min

    if (currentTsStr && nextTsStr) {
      const currentTs = new Date(currentTsStr).getTime();
      const nextTs = new Date(nextTsStr).getTime();
      if (!isNaN(currentTs) && !isNaN(nextTs)) {
        delay = nextTs - currentTs;
      }
    }

    // Clamp delay
    if (delay < 150) delay = 150;
    if (delay > 2000) delay = 2000;

    // Apply speed
    const visualDelay = delay / speed;

    timerRef.current = setTimeout(() => {
      playNext();
    }, visualDelay);

    return clearTimer;
  }, [isPlaying, currentIndex, speed, actualEvents, isFinished, clearTimer, playNext]);

  const startReplay = useCallback(() => {
    if (actualEvents.length === 0) return;
    setIsReplaying(true);
    if (currentIndex >= actualEvents.length - 1) {
      setCurrentIndex(0);
    }
    setIsPlaying(true);
  }, [actualEvents.length, currentIndex]);

  const pauseReplay = useCallback(() => {
    setIsPlaying(false);
  }, []);

  const restartReplay = useCallback(() => {
    setCurrentIndex(0);
    setIsPlaying(true);
    setIsReplaying(true);
  }, []);

  const reset = useCallback(() => {
    setIsReplaying(false);
    setIsPlaying(false);
    setCurrentIndex(0);
    clearTimer();
  }, [clearTimer]);

  const changeSpeed = useCallback((newSpeed: ReplaySpeed) => {
    setSpeed(newSpeed);
  }, []);

  return {
    state: {
      isReplaying,
      isPlaying,
      currentIndex,
      speed,
      visibleEvents,
      totalEvents,
      isFinished
    },
    actions: {
      startReplay,
      pauseReplay,
      restartReplay,
      reset,
      changeSpeed
    }
  };
}
