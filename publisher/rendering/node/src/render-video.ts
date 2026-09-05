import fs from 'node:fs';
import path from 'node:path';
import {renderVideo} from '@revideo/renderer';

function arg(name: string): string {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) {
    throw new Error(`Missing ${name}`);
  }
  return process.argv[index + 1];
}

async function main() {
  const specPath = arg('--spec');
  const output = path.resolve(arg('--output'));
  if (!output.endsWith('.mp4')) {
    throw new Error(`Renderer V2 video output must end in .mp4: ${output}`);
  }
  const outFile = output as `${string}.mp4`;
  const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  fs.mkdirSync(path.dirname(output), {recursive: true});

  const rendered = await renderVideo({
    projectFile: path.resolve('src/project.ts'),
    variables: {spec},
    settings: {
      outFile,
      workers: 1,
      logProgress: true,
      projectSettings: {
        exporter: {
          name: '@revideo/core/wasm',
        },
      },
      ffmpeg: {
        ffmpegLogLevel: 'error',
        ffmpegPath: 'ffmpeg',
      },
      puppeteer: {
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
      },
    },
  });

  const actual = path.resolve(rendered);
  if (actual !== output && fs.existsSync(actual)) {
    fs.copyFileSync(actual, output);
  }
  if (!fs.existsSync(output)) {
    throw new Error(`Revideo did not create ${output}; returned ${rendered}`);
  }
  console.log(JSON.stringify({status: 'REVIDEO_RENDER_OK', output}));
}

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exit(1);
});
