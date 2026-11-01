import { jsonLdString } from "@/lib/metadata";

/**
 * Inject JSON-LD schema.org markup with plain <script type="application/ld+json">
 * tags. (next/script with strategy="beforeInteractive" only queues the
 * payload for the client bootstrap in the App Router, so the markup was
 * missing from the server HTML that crawlers read.) Pass either a single
 * payload object or an array of payloads (each becomes its own script tag
 * so Google Rich Results Test validates them independently).
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
                <script
                    key={`${id}-${i}`}
                    id={i === 0 ? id : `${id}-${i}`}
                    type="application/ld+json"
                    dangerouslySetInnerHTML={{ __html: jsonLdString(p) }}
                />
            ))}
        </>
    );
}
