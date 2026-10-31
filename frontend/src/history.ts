import { useCallback, useReducer } from "react";

type State<T> = { past: T[]; present: T; future: T[] };

type Action<T> =
  | { type: "commit"; value: T }
  | { type: "reset"; value: T }
  | { type: "undo" }
  | { type: "redo" };

const LIMIT = 120;

function reducer<T>(state: State<T>, action: Action<T>): State<T> {
  switch (action.type) {
    case "commit":
      return {
        past: [...state.past.slice(-LIMIT + 1), state.present],
        present: action.value,
        future: [],
      };
    case "reset":
      return { past: [], present: action.value, future: [] };
    case "undo": {
      if (state.past.length === 0) return state;
      const previous = state.past[state.past.length - 1];
      return {
        past: state.past.slice(0, -1),
        present: previous,
        future: [state.present, ...state.future].slice(0, LIMIT),
      };
    }
    case "redo": {
      if (state.future.length === 0) return state;
      const next = state.future[0];
      return {
        past: [...state.past.slice(-LIMIT + 1), state.present],
        present: next,
        future: state.future.slice(1),
      };
    }
  }
}

export function useHistory<T>(initial: T) {
  const [state, dispatch] = useReducer(reducer<T>, { past: [], present: initial, future: [] });

  const commit = useCallback((value: T) => dispatch({ type: "commit", value }), []);
  const reset = useCallback((value: T) => dispatch({ type: "reset", value }), []);
  const undo = useCallback(() => dispatch({ type: "undo" }), []);
  const redo = useCallback(() => dispatch({ type: "redo" }), []);

  return {
    value: state.present,
    commit,
    reset,
    undo,
    redo,
    canUndo: state.past.length > 0,
    canRedo: state.future.length > 0,
  };
}
