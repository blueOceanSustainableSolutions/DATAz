import { PlayIcon, PauseIcon } from "@/components/Icons";
import { formatOverlayTimestamp } from "@/constants/numericalOverlay";

/**
 * OverlayPlaybackBar — floating timeline + transport controls (bottom-centre of the map).
 *
 * Play/pause and a scrubber. Speed and Step controls live in OverlayConfigPanel.
 */
export default function OverlayPlaybackBar({ player }) {
  const {
    index,
    count,
    playing,
    setPlaying,
    buffering,
    seek,
    timestamp,
  } = player;

  return (
    <div className="pointer-events-auto flex w-full items-center gap-12 rounded-8 border border-grey300 bg-surface px-14 py-10 shadow-md 768:gap-16">
      <button
        type="button"
        onClick={() => setPlaying((p) => !p)}
        aria-label={playing ? "Pause" : "Play"}
        className="flex h-[36px] w-[36px] shrink-0 items-center justify-center rounded-full bg-primary text-white transition media-hover:hover:bg-primaryHover"
      >
        {playing ? <PauseIcon /> : <PlayIcon />}
      </button>

      <div className="flex min-w-0 flex-1 flex-col gap-6">
        <div className="flex items-center justify-between gap-8">
          <span className="copy-small font-bold text-textPrimary">
            {formatOverlayTimestamp(timestamp)}
          </span>
          <span className="copy-extrasmall text-grey500">
            {buffering && <span className="mr-8 text-primary">buffering…</span>}
            frame {count ? index + 1 : 0} / {count}
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={Math.max(0, count - 1)}
          value={index}
          onChange={(e) => seek(Number(e.target.value))}
          aria-label="Scrub frames"
          className="h-4 w-full cursor-pointer appearance-none rounded-full bg-grey300 accent-primary"
        />
      </div>
    </div>
  );
}
