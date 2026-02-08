import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';

interface ErrorToastProps {
  message: string;
  onDismiss: () => void;
  type?: 'error' | 'warning';
}

export function ErrorToast({ message, onDismiss, type = 'error' }: ErrorToastProps) {
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        className={`fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg border ${
          type === 'error'
            ? 'bg-red-500/10 border-red-500/20 text-red-600 dark:text-red-400'
            : 'bg-yellow-500/10 border-yellow-500/20 text-yellow-600 dark:text-yellow-400'
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="flex-1">{message}</div>
          <button
            onClick={onDismiss}
            className="hover:opacity-70 transition-opacity"
            aria-label="Dismiss"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
