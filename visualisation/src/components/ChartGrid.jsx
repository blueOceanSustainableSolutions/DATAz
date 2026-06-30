import ChartCardController from "@/components/ChartCardController";

/**
 * Lays out the visible chart cards for the active tab. The orchestrator
 * (useSiteTabOrchestrator) decides which cards are visible and pre-scopes each
 * card's hydrotwins, so this is a thin layout wrapper: it receives a ready list
 * of `{ card, scopedHydrotwins }` and renders one ChartCardController each.
 */
export default function ChartGrid({ cards = [], siteId, startDate, endDate }) {
  return (
    // No horizontal padding: the cards span the full container width so they line
    // up edge-to-edge with the Map + Rail row above (which has none). pt-0 keeps
    // the grid flush against the tab row; TabRenderer supplies the bottom spacing.
    <div className="grid grid-cols-1 gap-16 pb-16 pt-0 768:pb-24">
      {cards.map(({ card, scopedHydrotwins }) => (
        <ChartCardController
          key={card.id}
          card={card}
          siteId={siteId}
          scopedHydrotwins={scopedHydrotwins}
          startDate={startDate}
          endDate={endDate}
        />
      ))}
    </div>
  );
}
