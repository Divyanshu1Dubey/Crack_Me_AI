import Script from "next/script";

/**
 * Inject JSON-LD schema.org markup into the document head (or body) using
 * Next.js's <Script strategy="beforeInteractive">. Pass either a single
 * payload object or an array of payloads (each will become its own script
 * tag so Google Rich Results Test will validate them independently).
 */
export default function StructuredData({
    id,
    data,
}: {
    id: string;
    data: object | object[];
}) {
    const payloads = Array.isArray(data) ? data : [data];
    return (
        <>
            {payloads.map((p, i) => (
                <Script
                    key={`${id}-${i}`}
                    id={i === 0 ? id : `${id}-${i}`}
                    type="application/ld+json"
                    strategy="beforeInteractive"
                    dangerouslySetInnerHTML={{ __html: JSON.stringify(p) }}
                />
            ))}
        </>
    );
}
