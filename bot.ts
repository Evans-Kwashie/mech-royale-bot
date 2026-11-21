import { log, run, type Hello } from "./src/mechfight.ts"
import { Brain } from "./src/bot.ts"

run((hello: Hello) => {
  for (const dir of [hello.map?.dir, "/arena"]) {
    if (!dir) continue
    try {
      return new Brain({ ...hello, map: { ...hello.map, dir } })
    } catch (error) {
      log("policy initialization failed with map dir " + dir, error)
    }
  }
  throw new Error("unable to initialize arena policy")
})
