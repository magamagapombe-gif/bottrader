import type { AppProps } from "next/app";
import Head from "next/head";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <title>SuperEye Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="theme-color" content="#0f1117" />
      </Head>
      <style global jsx>{`
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0f1117; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0f1117; }
        ::-webkit-scrollbar-thumb { background: #2d3148; border-radius: 3px; }
        input:focus, select:focus { outline: none; border-color: #00c896 !important; }
      `}</style>
      <Component {...pageProps} />
    </>
  );
}
