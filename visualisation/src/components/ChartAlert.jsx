import { Alert, AlertDescription, AlertTitle } from "@/components/Alert";
import { SpinnerIcon } from "@/components/Icons";

export const ChartAlert = ({ error, loading, hasData }) => {
  return (
    <>
      {!error && loading && (
        <div className="absolute w-full h-full inset-0 bg-surface/70 z-10 flex justify-center items-center">
          <SpinnerIcon extraClass="w-48 h-48 animate-spin text-primary" />
        </div>
      )}

      {error && (
        <div className="absolute w-full h-full inset-0 bg-surface/70 z-10 flex justify-center items-center">
          <Alert variant="error" className="!w-fit max-w-lg">
            <AlertTitle className="copy-body">
              {typeof error === "string" ? error : "There was an error"}
            </AlertTitle>
            <AlertDescription className="copy-small">
              Please try again later.
            </AlertDescription>
          </Alert>
        </div>
      )}

      {!error && !loading && !hasData && (
        <div className="absolute w-full h-full inset-0 bg-surface/70 z-10 flex justify-center items-center">
          <Alert variant="info" className="!w-fit max-w-lg">
            <AlertTitle className="copy-body">No data available</AlertTitle>
            <AlertDescription className="copy-small">
              There is no data to display for the selected time range.
            </AlertDescription>
          </Alert>
        </div>
      )}
    </>
  );
};

export default ChartAlert;
