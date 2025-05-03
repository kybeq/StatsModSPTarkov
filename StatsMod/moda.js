// mod.js - Wersja z patchowaniem STARTU i KOŃCA + ZAPISYWANIE JSON DO PLIKÓW DEBUG

const fs = require("fs");
const path = require("path");

class DetailedStatsTrackerFikaFinalPatch {
  constructor() {
    this.logger = null;
    this.jsonUtil = null;
    this.databaseServer = null;
    this.saveServer = null;
    this.profileHelper = null;
    this.ragfairPriceService = null;
    this.fikaInsuranceServiceInstance = null;
    this.locationLifecycleServiceInstance = null;

    this.persistentStats = {};
    this.modConfig = {};
    this.currentRaidInfo = null;

    // Utwórz folder debug_logs, jeśli nie istnieje
    this.ensureDebugLogFolderExists();

    this.setDefaultConfig();
    this.initializePersistentStats();
  }

  // --- Funkcja pomocnicza do tworzenia folderu debug ---
  ensureDebugLogFolderExists() {
    const debugFolderPath = path.join(__dirname, "debug_logs");
    try {
      if (!fs.existsSync(debugFolderPath)) {
        fs.mkdirSync(debugFolderPath, { recursive: true });
        // Loguj tylko jeśli logger już istnieje (może być wywołane przed preSptLoad)
        if (this.logger) {
          this.logger.log(
            `[StatTrackerFinalPatch] Created debug log folder: ${debugFolderPath}`,
            "yellow"
          );
        } else {
          console.log(
            `[StatTrackerFinalPatch] Created debug log folder: ${debugFolderPath}`
          );
        }
      }
    } catch (e) {
      if (this.logger) {
        this.logger.error(
          `[StatTrackerFinalPatch] Could not create debug log folder: ${e}`
        );
      } else {
        console.error(
          `[StatTrackerFinalPatch] Could not create debug log folder: ${e}`
        );
      }
    }
  }

  // --- Haki SPT-Aki ---
  preSptLoad(container) {
    try {
      console.log(
        "[StatTrackerFinalPatch] !!! --- Entering preSptLoad --- !!!"
      );
      this.logger = container.resolve("WinstonLogger");
      if (this.logger)
        this.logger.log(
          "[StatTrackerFinalPatch] Logger resolved successfully.",
          "green"
        );
      else
        console.error(
          "[StatTrackerFinalPatch] FAILED to resolve WinstonLogger!"
        );
    } catch (e) {
      console.error(
        `[StatTrackerFinalPatch] CRITICAL ERROR during preSptLoad: ${e}`
      );
    }
    // Upewnij się, że folder istnieje po załadowaniu loggera
    this.ensureDebugLogFolderExists();
  }

  postDBLoad(container) {
    if (!this.logger) {
      console.error(
        "[StatTrackerFinalPatch] Logger not initialized. Aborting postDBLoad."
      );
      return;
    }
    this.logger.log(
      `[StatTrackerFinalPatch] Entering postDBLoad. Logger is OK.`,
      "yellow"
    );

    try {
      // Inicjalizacja serwisów SPT
      this.jsonUtil = container.resolve("JsonUtil");
      this.databaseServer = container.resolve("DatabaseServer");
      this.saveServer = container.resolve("SaveServer");
      this.profileHelper = container.resolve("ProfileHelper");
      this.ragfairPriceService = container.resolve("RagfairPriceService");
      try {
        container.resolve("StaticRouterModService");
      } catch (e) {
        /* Ignoruj */
      }

      if (
        !this.jsonUtil ||
        !this.databaseServer ||
        !this.saveServer ||
        !this.profileHelper
      ) {
        this.logger.error(
          "[StatTrackerFinalPatch] Failed to resolve one or more core SPT services."
        );
      } else {
        this.logger.log(
          "[StatTrackerFinalPatch] Core SPT services resolved successfully.",
          "green"
        );
      }

      // Patchowanie
      this.attemptFikaPatchStart(container);
      this.attemptFikaPatchEnd(container);

      // Ładowanie config/stats
      this.loadConfig();
      this.loadPersistentStats();

      this.logger.log(
        "[StatTrackerFinalPatch] Mod finished postDBLoad initialization phase.",
        "cyan"
      );
    } catch (e) {
      this.logger.error(
        `[StatTrackerFinalPatch] CRITICAL ERROR during postDBLoad: ${e}\n${e.stack}`
      );
    }
  }

  // --- Funkcja do Patchowania Startu Rajdu ---
  attemptFikaPatchStart(container) {
    this.logger.log(
      "[StatTrackerFinalPatch] Attempting to patch LocationLifecycleService.startLocalRaid...",
      "yellow"
    );
    try {
      const locationService = container.resolve("LocationLifecycleService");
      if (
        locationService &&
        typeof locationService.startLocalRaid === "function"
      ) {
        this.logger.log(
          "[StatTrackerFinalPatch] LocationLifecycleService instance resolved successfully.",
          "green"
        );
        this.locationLifecycleServiceInstance = locationService;
        const originalStartLocalRaid = locationService.startLocalRaid;
        this.logger.log(
          "[StatTrackerFinalPatch] Original startLocalRaid method stored.",
          "grey"
        );

        locationService.startLocalRaid = (sessionId, request) => {
          this.logger.log(
            `[StatTrackerFinalPatch] === LocationLifecycleService.startLocalRaid PATCHED! Session: ${sessionId} ===`,
            "cyan"
          );
          let originalResult = null;
          try {
            this.logger.log(
              "[StatTrackerFinalPatch] Calling original LocationLifecycleService.startLocalRaid...",
              "grey"
            );
            originalResult = originalStartLocalRaid.call(
              locationService,
              sessionId,
              request
            );
            this.logger.log(
              "[StatTrackerFinalPatch] Original startLocalRaid finished.",
              "grey"
            );
          } catch (e) {
            /* ... obsługa błędu ... */ return originalResult;
          }

          this.logger.log(
            "[StatTrackerFinalPatch] Executing custom raid start processing...",
            "yellow"
          );
          try {
            // --- ZAPIS JSON DO PLIKU ---
            this.saveJsonToDebugFile(
              `startLocalRaid_request_${sessionId}_${Date.now()}.json`,
              request
            );
            this.saveJsonToDebugFile(
              `startLocalRaid_result_${sessionId}_${Date.now()}.json`,
              originalResult
            );
            // --- KONIEC ZAPISU ---

            let pmcData = null;
            // ... (logika pobierania pmcData jak poprzednio) ...
            if (this.profileHelper) {
              try {
                pmcData =
                  this.profileHelper.getPmcProfile(sessionId) ||
                  this.profileHelper.getFullProfile(sessionId);
                if (!pmcData)
                  this.logger.error(`...Failed to fetch pmcData...`);
                else this.logger.log(`...Successfully fetched pmcData...`);
              } catch (e) {
                this.logger.error(`...Error fetching profile...: ${e}`);
              }
            } else {
              this.logger.error("ProfileHelper missing");
            }

            const mapName = request?.location?.toLowerCase() || "unknown";
            const timeOfDay =
              request?.timeAndWeatherSettings?.timeVariant ||
              originalResult?.locationLoot?.TimeAndWeatherSettings
                ?.timeVariant ||
              "unknown";

            if (sessionId && pmcData && this.jsonUtil) {
              try {
                this.currentRaidInfo = null;
                this.currentRaidInfo = {
                  /* ... jak poprzednio ... */
                };
                this.logger.log(
                  `[StatTrackerFinalPatch] >>> CAPTURED Raid Start Info! Session: ${sessionId}, Map: ${mapName}`,
                  "green"
                );
              } catch (cloneError) {
                /* ... obsługa błędu ... */
              }
            } else {
              this.logger.error(
                `[StatTrackerFinalPatch] Failed to capture essential raid start data.`
              );
            }
          } catch (e) {
            this.logger.error(
              `[StatTrackerFinalPatch] Error during custom start processing: ${e}\n${e.stack}`
            );
          }
          return originalResult;
        };
        this.logger.log(
          "[StatTrackerFinalPatch] LocationLifecycleService.startLocalRaid patched successfully!",
          "green"
        );
      } else {
        this.logger.error(
          "[StatTrackerFinalPatch] FAILED to resolve LocationLifecycleService or its startLocalRaid method!",
          "red"
        );
      }
    } catch (e) {
      this.logger.error(
        `[StatTrackerFinalPatch] CRITICAL Error resolving or patching LocationLifecycleService: ${e}\n${e.stack}`
      );
    }
  }

  // --- Funkcja do Patchowania Końca Rajdu ---
  attemptFikaPatchEnd(container) {
    this.logger.log(
      "[StatTrackerFinalPatch] Attempting to patch FikaInsuranceService.onEndLocalRaidRequest...",
      "yellow"
    );
    try {
      const fikaInsuranceService = container.resolve("FikaInsuranceService");
      if (
        fikaInsuranceService &&
        typeof fikaInsuranceService.onEndLocalRaidRequest === "function"
      ) {
        this.logger.log(
          "[StatTrackerFinalPatch] FikaInsuranceService instance resolved successfully.",
          "green"
        );
        this.fikaInsuranceServiceInstance = fikaInsuranceService;
        const originalOnEndLocalRaidRequest =
          fikaInsuranceService.onEndLocalRaidRequest;
        this.logger.log(
          "[StatTrackerFinalPatch] Original onEndLocalRaidRequest method stored.",
          "grey"
        );

        fikaInsuranceService.onEndLocalRaidRequest = (
          sessionId,
          matchId,
          request
        ) => {
          this.logger.log(
            `[StatTrackerFinalPatch] === FikaInsuranceService.onEndLocalRaidRequest PATCHED! Session: ${sessionId}, MatchId: ${matchId} ===`,
            "magenta"
          );
          try {
            /* ... wywołanie oryginału ... */ originalOnEndLocalRaidRequest.call(
              fikaInsuranceService,
              sessionId,
              matchId,
              request
            );
          } catch (e) {
            /* ... obsługa błędu ... */
          }

          this.logger.log(
            "[StatTrackerFinalPatch] Executing custom raid end processing...",
            "cyan"
          );
          try {
            // --- ZAPIS JSON DO PLIKU ---
            this.saveJsonToDebugFile(
              `onEndLocalRaidRequest_request_${sessionId}_${Date.now()}.json`,
              request
            );
            // --- KONIEC ZAPISU ---

            if (
              !this.currentRaidInfo ||
              this.currentRaidInfo.sessionId !== sessionId
            ) {
              /* ... obsługa braku danych startowych ... */ return;
            }

            const exitStatus = request?.exit?.toLowerCase() || "unknown";
            const exitName = request?.exitName || null;
            const offraidData = request?.profile;

            if (
              offraidData &&
              typeof offraidData === "object" &&
              offraidData.Info &&
              offraidData.Inventory &&
              offraidData.Stats
            ) {
              this.logger.log(
                `[StatTrackerFinalPatch] <<< Found VALID offraidData in patched request! Session: ${sessionId}, Status: ${exitStatus}`,
                "green"
              );
              // --- ZAPIS OFFRIDEDATA DO PLIKU (OPCJONALNE, MOŻE BYĆ W GŁÓWNYM PLIKU REQUEST) ---
              // this.saveJsonToDebugFile(`offraidData_${sessionId}_${Date.now()}.json`, offraidData);
              // --- KONIEC ZAPISU ---
              this.processRaidEndData(
                sessionId,
                exitStatus,
                exitName,
                offraidData
              );
            } else {
              /* ... obsługa braku offraidData ... */ this.currentRaidInfo =
                null;
            }
          } catch (e) {
            /* ... obsługa błędu ... */ this.currentRaidInfo = null;
          }
        };
        this.logger.log(
          "[StatTrackerFinalPatch] FikaInsuranceService.onEndLocalRaidRequest patched successfully!",
          "green"
        );
      } else {
        this.logger.error(
          "[StatTrackerFinalPatch] FAILED to resolve FikaInsuranceService or its method!",
          "red"
        );
      }
    } catch (e) {
      this.logger.error(
        `[StatTrackerFinalPatch] CRITICAL Error resolving or patching FikaInsuranceService: ${e}\n${e.stack}`
      );
    }
  }

  // --- Funkcja Pomocnicza do Zapisu JSON ---
  saveJsonToDebugFile(filename, data) {
    if (!this.logger || !this.jsonUtil) {
      console.error(
        `[StatTrackerFinalPatch] Cannot save debug JSON - logger or jsonUtil missing.`
      );
      return;
    }
    try {
      const debugFolderPath = path.join(__dirname, "debug_logs");
      // Upewnij się, że folder istnieje (ponownie, na wszelki wypadek)
      if (!fs.existsSync(debugFolderPath)) {
        fs.mkdirSync(debugFolderPath, { recursive: true });
      }
      const filePath = path.join(debugFolderPath, filename);
      const jsonData = this.jsonUtil.serialize(data, true); // true = pretty print
      fs.writeFileSync(filePath, jsonData, "utf8");
      this.logger.log(
        `[StatTrackerFinalPatch] Saved debug data to: ${filePath}`,
        "blue"
      );
    } catch (e) {
      this.logger.error(
        `[StatTrackerFinalPatch] Failed to save debug JSON to file ${filename}: ${e}`
      );
      // Loguj surowe dane, jeśli zapis zawiódł
      console.log("Raw data that failed to save:");
      console.log(data);
    }
  }

  // --- Funkcja Pomocnicza do Logowania Obiektów (bez zmian) ---
  logObjectDataForDebugging(label, data) {
    if (!this.logger || !this.jsonUtil) return;
    try {
      const serializedData = this.jsonUtil.serialize(data, true, 4);
      this.logger.log(
        `[StatTrackerFinalPatch] --- ${label} --- \n${serializedData}`,
        "grey"
      );
    } catch (e) {
      this.logger.error(
        `[StatTrackerFinalPatch] Error serializing data for label "${label}": ${e}`
      );
      console.log(`[StatTrackerFinalPatch] --- ${label} (raw data) --- `);
      console.log(data);
    }
  }

  // --- processRaidEndData (bez zmian) ---
  processRaidEndData(sessionId, exitStatus, exitName, offraidData) {
    /* ... jak poprzednio ... */
  }
  // --- Standardowe hooki (ignorowane) ---
  onRaidStart(url, info, sessionId, pmcData) {
    /* Ignored */
  }
  onRaidEnd(url, info, sessionId, exitStatus, exitName, offraidData) {
    /* Ignored */
  }
  // --- Metody Pomocnicze (loadConfig, saveConfig, etc. - bez zmian) ---
  loadConfig() {
    /* ... jak poprzednio ... */
  }
  setDefaultConfig() {
    /* ... jak poprzednio ... */
  }
  ensureDefaultConfigValues() {
    /* ... jak poprzednio ... */
  }
  saveConfig() {
    /* ... jak poprzednio ... */
  }
  loadPersistentStats() {
    /* ... jak poprzednio ... */
  }
  initializePersistentStats() {
    /* ... jak poprzednio ... */
  }
  savePersistentStats() {
    /* ... jak poprzednio ... */
  }
  updatePersistentStats(processedRaidStats) {
    /* ... jak poprzednio ... */
  }
}

// Rejestracja modu
module.exports = { mod: new DetailedStatsTrackerFikaFinalPatch() };

// --- Skrócone wersje metod pomocniczych dla zwięzłości (w pełnym kodzie są całe) ---
DetailedStatsTrackerFikaFinalPatch.prototype.loadConfig = function () {
  if (!this.jsonUtil || !this.logger) {
    console.error(
      "[StatTrackerFinalPatch] Cannot load config: JsonUtil or Logger not initialized!"
    );
    this.setDefaultConfig();
    return;
  }
  const configPath = path.join(__dirname, "config", "config.json");
  this.logger.log(
    `[StatTrackerFinalPatch] Attempting to load config using 'fs' from: ${configPath}`,
    "grey"
  );
  try {
    if (fs.existsSync(configPath)) {
      const configContent = fs.readFileSync(configPath, "utf8");
      this.modConfig = this.jsonUtil.deserialize(configContent);
      this.logger.log(
        "[StatTrackerFinalPatch] Configuration loaded successfully using 'fs'.",
        "green"
      );
      this.ensureDefaultConfigValues();
    } else {
      this.logger.warning(
        `[StatTrackerFinalPatch] Config file not found at ${configPath}. Using default config and attempting to save it.`
      );
      this.setDefaultConfig();
      this.saveConfig();
    }
  } catch (e) {
    this.logger.error(
      `[StatTrackerFinalPatch] Error using 'fs' to load config: ${e}. Using default config.`
    );
    this.setDefaultConfig();
  }
};
DetailedStatsTrackerFikaFinalPatch.prototype.setDefaultConfig = function () {
  this.modConfig = {
    enabled: true,
    trackKills: true,
    trackLootValue: false,
    maxRaidHistory: 50,
    persistentStatsFilePath: "stats_data.json",
  };
  if (this.logger)
    this.logger.log(
      "[StatTrackerFinalPatch] Default configuration set/reset.",
      "yellow"
    );
  else console.log("[StatTrackerFinalPatch] Default configuration set/reset.");
};
DetailedStatsTrackerFikaFinalPatch.prototype.ensureDefaultConfigValues =
  function () {
    const defaultConfig = {
      enabled: true,
      trackKills: true,
      trackLootValue: false,
      maxRaidHistory: 50,
      persistentStatsFilePath: "stats_data.json",
    };
    let changed = false;
    for (const key in defaultConfig) {
      if (this.modConfig[key] === undefined) {
        this.modConfig[key] = defaultConfig[key];
        changed = true;
      }
    }
    if (changed && this.logger)
      this.logger.log(
        "[StatTrackerFinalPatch] Added missing default values to loaded config.",
        "yellow"
      );
  };
DetailedStatsTrackerFikaFinalPatch.prototype.saveConfig = function () {
  if (!this.jsonUtil || !this.logger) {
    console.error(
      "[StatTrackerFinalPatch] Cannot save config: JsonUtil or Logger not initialized!"
    );
    return;
  }
  const configPath = path.join(__dirname, "config", "config.json");
  const configDir = path.join(__dirname, "config");
  try {
    if (!fs.existsSync(configDir)) {
      this.logger.log(
        `[StatTrackerFinalPatch] Creating config directory using 'fs': ${configDir}`,
        "yellow"
      );
      fs.mkdirSync(configDir, { recursive: true });
    }
    this.logger.log(
      `[StatTrackerFinalPatch] Saving config file using 'fs' to: ${configPath}`,
      "grey"
    );
    fs.writeFileSync(
      configPath,
      this.jsonUtil.serialize(this.modConfig, true),
      "utf8"
    );
  } catch (e) {
    this.logger.error(
      `[StatTrackerFinalPatch] Could not save config file using 'fs': ${e}`
    );
  }
};
DetailedStatsTrackerFikaFinalPatch.prototype.loadPersistentStats = function () {
  if (!this.jsonUtil || !this.logger) {
    console.error(
      "[StatTrackerFinalPatch] Cannot load persistent stats: JsonUtil or Logger not initialized!"
    );
    this.initializePersistentStats();
    return;
  }
  const relativePath =
    this.modConfig.persistentStatsFilePath || "stats_data.json";
  const filePath = path.join(__dirname, relativePath);
  this.logger.log(
    `[StatTrackerFinalPatch] Attempting to load persistent stats using 'fs' from: ${filePath}`,
    "grey"
  );
  try {
    if (fs.existsSync(filePath)) {
      const fileContent = fs.readFileSync(filePath, "utf8");
      this.persistentStats = this.jsonUtil.deserialize(fileContent);
      if (
        typeof this.persistentStats !== "object" ||
        this.persistentStats === null ||
        Object.keys(this.persistentStats).length === 0
      ) {
        this.logger.warning(
          "[StatTrackerFinalPatch] Loaded persistent stats file seems empty or corrupted. Initializing empty stats."
        );
        this.initializePersistentStats();
      } else {
        this.logger.log(
          "[StatTrackerFinalPatch] Persistent stats loaded successfully using 'fs'.",
          "green"
        );
      }
    } else {
      this.logger.warning(
        `[StatTrackerFinalPatch] Persistent stats file not found at ${filePath}. Initializing empty stats.`
      );
      this.initializePersistentStats();
    }
  } catch (e) {
    this.logger.error(
      `[StatTrackerFinalPatch] Error using 'fs' to load stats: ${e}. Initializing empty stats.`
    );
    this.initializePersistentStats();
  }
};
DetailedStatsTrackerFikaFinalPatch.prototype.initializePersistentStats =
  function () {
    this.persistentStats = {
      totalRaids: 0,
      totalSurvived: 0,
      totalKills: { pmc: 0, scav: 0, boss: 0, other: 0 },
      totalExp: 0,
      averageSurvivalRate: 0,
      raidHistory: [],
      playerStatsSnapshot: {},
    };
    if (this.logger)
      this.logger.log(
        "[StatTrackerFinalPatch] Initialized/reset empty persistent stats object.",
        "yellow"
      );
    else
      console.log(
        "[StatTrackerFinalPatch] Initialized/reset empty persistent stats object."
      );
  };
DetailedStatsTrackerFikaFinalPatch.prototype.savePersistentStats = function () {
  if (!this.jsonUtil || !this.logger) {
    console.error(
      "[StatTrackerFinalPatch] Cannot save persistent stats: JsonUtil or Logger not initialized!"
    );
    return;
  }
  const relativePath =
    this.modConfig.persistentStatsFilePath || "stats_data.json";
  const filePath = path.join(__dirname, relativePath);
  try {
    const modDir = __dirname;
    fs.writeFileSync(
      filePath,
      this.jsonUtil.serialize(this.persistentStats, true),
      "utf8"
    );
  } catch (e) {
    this.logger.error(
      `[StatTrackerFinalPatch] Could not save persistent stats file using 'fs': ${e}`
    );
  }
};
DetailedStatsTrackerFikaFinalPatch.prototype.updatePersistentStats = function (
  processedRaidStats
) {
  if (!this.logger) {
    console.error("Cannot update stats, logger missing");
    return;
  }
  this.logger.log(
    `[StatTrackerFinalPatch] Updating persistent stats with data from raid on ${processedRaidStats.map}.`,
    "grey"
  );
  if (!this.persistentStats || typeof this.persistentStats !== "object")
    this.initializePersistentStats();
  if (
    !this.persistentStats.totalKills ||
    typeof this.persistentStats.totalKills !== "object"
  )
    this.persistentStats.totalKills = { pmc: 0, scav: 0, boss: 0, other: 0 };
  if (!Array.isArray(this.persistentStats.raidHistory))
    this.persistentStats.raidHistory = [];
  this.persistentStats.totalRaids = (this.persistentStats.totalRaids || 0) + 1;
  if (processedRaidStats.status === "survived")
    this.persistentStats.totalSurvived =
      (this.persistentStats.totalSurvived || 0) + 1;
  if (processedRaidStats.kills && Array.isArray(processedRaidStats.kills)) {
    for (const kill of processedRaidStats.kills) {
      const role = kill.role?.toLowerCase() || "other";
      if (role.includes("bear") || role.includes("usec"))
        this.persistentStats.totalKills.pmc =
          (this.persistentStats.totalKills.pmc || 0) + 1;
      else if (role.includes("savage") || role.includes("playerscav"))
        this.persistentStats.totalKills.scav =
          (this.persistentStats.totalKills.scav || 0) + 1;
      else if (role.includes("boss"))
        this.persistentStats.totalKills.boss =
          (this.persistentStats.totalKills.boss || 0) + 1;
      else
        this.persistentStats.totalKills.other =
          (this.persistentStats.totalKills.other || 0) + 1;
    }
  }
  this.persistentStats.totalExp =
    (this.persistentStats.totalExp || 0) + (processedRaidStats.expGained || 0);
  this.persistentStats.averageSurvivalRate =
    this.persistentStats.totalRaids > 0
      ? parseFloat(
          (
            (this.persistentStats.totalSurvived /
              this.persistentStats.totalRaids) *
            100
          ).toFixed(2)
        )
      : 0;
  this.persistentStats.raidHistory.push(processedRaidStats);
  const maxHistory = this.modConfig.maxRaidHistory || 50;
  if (this.persistentStats.raidHistory.length > maxHistory)
    this.persistentStats.raidHistory.shift();
  this.logger.log("[StatTrackerFinalPatch] Persistent stats updated.", "green");
};
DetailedStatsTrackerFikaFinalPatch.prototype.processRaidEndData = function (
  sessionId,
  exitStatus,
  exitName,
  offraidData
) {
  if (!this.currentRaidInfo || this.currentRaidInfo.sessionId !== sessionId) {
    if (this.logger)
      this.logger.error(
        "[StatTrackerFinalPatch] processRaidEndData called with invalid session or missing currentRaidInfo!"
      );
    this.currentRaidInfo = null;
    return;
  }
  if (!this.logger || !this.databaseServer || !this.jsonUtil) {
    console.error(
      "[StatTrackerFinalPatch] Cannot process raid end data - core services missing!"
    );
    this.currentRaidInfo = null;
    return;
  }
  if (!this.currentRaidInfo) {
    if (this.logger)
      this.logger.warning(
        `[StatTrackerFinalPatch] Attempted to process raid end data for session ${sessionId} again. Skipping.`
      );
    return;
  }
  const raidInfo = this.currentRaidInfo;
  this.currentRaidInfo = null;
  const endTime = Date.now();
  const durationSeconds = Math.floor((endTime - raidInfo.startTime) / 1000);
  const raidResult = exitStatus;
  this.logger.log(
    `[StatTrackerFinalPatch] Processing FULL Raid End Data. Session: ${sessionId}, Status: ${raidResult}, Time: ${durationSeconds}s`,
    "cyan"
  );
  try {
    const processedRaidStats = {
      map: raidInfo.map,
      startTime: raidInfo.startTime,
      endTime: endTime,
      durationSeconds: durationSeconds,
      timeOfDay: raidInfo.timeOfDay,
      weather: raidInfo.weather,
      status: raidResult,
      exitName: exitName || "N/A",
      kills: [],
      loot: { itemsAdded: [], itemsRemoved: [], totalValueGained: 0 },
      expGained: 0,
      skillProgress: {},
      damageDealt: 0,
      shotsFired: 0,
      shotsHit: 0,
      headshots: 0,
    };
    if (offraidData.Stats?.OverallCounters?.Counters) {
      const counters = offraidData.Stats.OverallCounters.Counters;
      const findCounter = (key) =>
        counters.find((c) => c.Key === key)?.Value || 0;
      processedRaidStats.shotsFired = findCounter("Shots");
      processedRaidStats.shotsHit = findCounter("Hits");
      processedRaidStats.headshots = findCounter("Headshots");
    }
    processedRaidStats.expGained = offraidData.experience || 0;
    if (offraidData.Stats?.Victims) {
      const dbItems = this.databaseServer.getTables().templates.items;
      for (const victim of offraidData.Stats.Victims) {
        let weaponName = "Unknown";
        if (victim.Weapon && dbItems[victim.Weapon]?._name)
          weaponName = dbItems[victim.Weapon]._name;
        else if (victim.Weapon) weaponName = victim.Weapon;
        processedRaidStats.kills.push({
          name: victim.Name || "?",
          role: victim.Role || "?",
          level: victim.Level || 0,
          weapon: weaponName,
          distance: victim.Distance || 0,
          bodyPart: victim.BodyPart || "?",
          time: victim.Time || 0,
        });
      }
      this.logger.log(
        `[StatTrackerFinalPatch] Processed ${processedRaidStats.kills.length} kills for raid ${sessionId}.`,
        "grey"
      );
    } else {
      this.logger.log(
        `[StatTrackerFinalPatch] No victim data in offraidData.Stats for raid ${sessionId}.`,
        "grey"
      );
    }
    this.updatePersistentStats(processedRaidStats);
    this.savePersistentStats();
  } catch (e) {
    this.logger.error(
      `[StatTrackerFinalPatch] Error during processRaidEndData logic: ${e}\n${e.stack}`
    );
  } finally {
    if (this.logger)
      this.logger.log(
        `[StatTrackerFinalPatch] Finished full raid end processing for session ${sessionId}.`,
        "grey"
      );
  }
};
