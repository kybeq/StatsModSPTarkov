// mod.js - Wersja używająca console.log zamiast this.logger.log

const fs = require("fs");
const path = require("path");

class DetailedStatsTrackerFikaFinalPatch {
  constructor() {
    this.logger = null; // Nadal próbujemy go zainicjalizować dla error/warning
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

    this.ensureDebugLogFolderExists();
    this.setDefaultConfig();
    this.initializePersistentStats();
  }

  ensureDebugLogFolderExists() {
    const debugFolderPath = path.join(__dirname, "debug_logs");
    try {
      if (!fs.existsSync(debugFolderPath)) {
        fs.mkdirSync(debugFolderPath, { recursive: true });
        // Używamy console.log
        console.log(
          `[StatTrackerFinalPatch] Created debug log folder: ${debugFolderPath}`
        );
      }
    } catch (e) {
      // Używamy console.error
      console.error(
        `[StatTrackerFinalPatch] Could not create debug log folder: ${e}`
      );
    }
  }

  preSptLoad(container) {
    try {
      console.log(
        "[StatTrackerFinalPatch] !!! --- Entering preSptLoad --- !!!"
      );
      // Nadal próbujemy zainicjalizować logger dla error/warning
      try {
        this.logger = container.resolve("WinstonLogger");
        if (this.logger)
          console.log(
            "[StatTrackerFinalPatch] Logger resolved successfully (for errors/warnings)."
          );
        else
          console.error(
            "[StatTrackerFinalPatch] FAILED to resolve WinstonLogger!"
          );
      } catch (e) {
        console.error(
          `[StatTrackerFinalPatch] Error resolving WinstonLogger: ${e}`
        );
      }
      console.log("[StatTrackerFinalPatch] --- Exiting preSptLoad ---"); // Używamy console.log
    } catch (e) {
      console.error(
        `[StatTrackerFinalPatch] CRITICAL ERROR during preSptLoad: ${e}`
      );
    }
    this.ensureDebugLogFolderExists(); // Upewnij się, że folder istnieje
  }

  postDBLoad(container) {
    // Sprawdzenie loggera jest teraz mniej krytyczne, bo używamy console.log
    if (!this.logger) {
      console.warn(
        "[StatTrackerFinalPatch] Logger was not initialized in preSptLoad. Error/Warning logs might be missing."
      );
    }
    console.log(`[StatTrackerFinalPatch] Entering postDBLoad.`); // Używamy console.log

    try {
      // Inicjalizacja serwisów SPT
      this.jsonUtil = container.resolve("JsonUtil");
      this.databaseServer = container.resolve("DatabaseServer");
      this.saveServer = container.resolve("SaveServer");
      this.profileHelper = container.resolve("ProfileHelper");
      this.ragfairPriceService = container.resolve("RagfairPriceService");
      try {
        container.resolve("StaticRouterModService");
      } catch (e) {}

      if (
        !this.jsonUtil ||
        !this.databaseServer ||
        !this.saveServer ||
        !this.profileHelper
      ) {
        // Używamy logger.error jeśli dostępny, inaczej console.error
        (this.logger || console).error(
          "[StatTrackerFinalPatch] Failed to resolve one or more core SPT services."
        );
      } else {
        console.log(
          "[StatTrackerFinalPatch] Core SPT services resolved successfully."
        ); // Używamy console.log
      }

      // Patchowanie
      this.attemptFikaPatchStart(container);
      this.attemptFikaPatchEnd(container);

      // Ładowanie config/stats
      this.loadConfig();
      this.loadPersistentStats();

      console.log(
        "[StatTrackerFinalPatch] Mod finished postDBLoad initialization phase."
      ); // Używamy console.log
    } catch (e) {
      (this.logger || console).error(
        `[StatTrackerFinalPatch] CRITICAL ERROR during postDBLoad: ${e}\n${e.stack}`
      );
    }
  }

  // --- Funkcja do Patchowania Startu Rajdu ---
  attemptFikaPatchStart(container) {
    console.log(
      "[StatTrackerFinalPatch] Attempting to patch LocationLifecycleService.startLocalRaid..."
    ); // Używamy console.log
    try {
      const locationService = container.resolve("LocationLifecycleService");
      if (
        locationService &&
        typeof locationService.startLocalRaid === "function"
      ) {
        console.log(
          "[StatTrackerFinalPatch] LocationLifecycleService instance resolved successfully."
        ); // Używamy console.log
        this.locationLifecycleServiceInstance = locationService;
        const originalStartLocalRaid = locationService.startLocalRaid;
        console.log(
          "[StatTrackerFinalPatch] Original startLocalRaid method stored."
        ); // Używamy console.log

        locationService.startLocalRaid = (sessionId, request) => {
          console.log(
            `[StatTrackerFinalPatch] === LocationLifecycleService.startLocalRaid PATCHED! Session: ${sessionId} ===`
          ); // Używamy console.log
          let originalResult = null;
          try {
            console.log(
              "[StatTrackerFinalPatch] Calling original LocationLifecycleService.startLocalRaid..."
            ); // Używamy console.log
            originalResult = originalStartLocalRaid.call(
              locationService,
              sessionId,
              request
            );
            console.log(
              "[StatTrackerFinalPatch] Original startLocalRaid finished."
            ); // Używamy console.log
          } catch (e) {
            (this.logger || console).error(
              `[StatTrackerFinalPatch] Error calling original startLocalRaid: ${e}\n${e.stack}`
            );
            return originalResult;
          }

          console.log(
            "[StatTrackerFinalPatch] Executing custom raid start processing..."
          ); // Używamy console.log
          try {
            this.saveJsonToDebugFile(
              `startLocalRaid_request_${sessionId}_${Date.now()}.json`,
              request
            );
            this.saveJsonToDebugFile(
              `startLocalRaid_result_${sessionId}_${Date.now()}.json`,
              originalResult
            );

            let pmcData = null;
            if (this.profileHelper) {
              try {
                pmcData =
                  this.profileHelper.getPmcProfile(sessionId) ||
                  this.profileHelper.getFullProfile(sessionId);
                if (pmcData && this.jsonUtil)
                  console.log(
                    `[StatTrackerFinalPatch] Successfully fetched pmcData for session ${sessionId}.`
                  );
                else
                  (this.logger || console).error(
                    `[StatTrackerFinalPatch] Failed to fetch pmcData for session ${sessionId}.`
                  );
              } catch (e) {
                (this.logger || console).error(
                  `[StatTrackerFinalPatch] Error fetching profile with ProfileHelper: ${e}`
                );
              }
            } else {
              (this.logger || console).error(
                "[StatTrackerFinalPatch] ProfileHelper not available."
              );
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
                  sessionId: sessionId,
                  profileAtStart: this.jsonUtil.clone(pmcData),
                  map: mapName,
                  startTime: Date.now(),
                  timeOfDay: timeOfDay,
                };
                console.log(
                  `[StatTrackerFinalPatch] >>> CAPTURED Raid Start Info! Session: ${sessionId}, Map: ${mapName}`
                ); // Używamy console.log
              } catch (cloneError) {
                (this.logger || console).error(
                  `[StatTrackerFinalPatch] Error cloning pmcData: ${cloneError}`
                );
                this.currentRaidInfo = null;
              }
            } else {
              (this.logger || console).error(
                `[StatTrackerFinalPatch] Failed to capture essential raid start data (sessionId, pmcData).`
              );
            }
          } catch (e) {
            (this.logger || console).error(
              `[StatTrackerFinalPatch] Error during custom start processing: ${e}\n${e.stack}`
            );
          }
          return originalResult;
        };
        console.log(
          "[StatTrackerFinalPatch] LocationLifecycleService.startLocalRaid patched successfully!"
        ); // Używamy console.log
      } else {
        (this.logger || console).error(
          "[StatTrackerFinalPatch] FAILED to resolve LocationLifecycleService or its startLocalRaid method!"
        );
      }
    } catch (e) {
      (this.logger || console).error(
        `[StatTrackerFinalPatch] CRITICAL Error resolving or patching LocationLifecycleService: ${e}\n${e.stack}`
      );
    }
  }

  // --- Funkcja do Patchowania Końca Rajdu ---
  attemptFikaPatchEnd(container) {
    console.log(
      "[StatTrackerFinalPatch] Attempting to patch FikaInsuranceService.onEndLocalRaidRequest..."
    ); // Używamy console.log
    try {
      const fikaInsuranceService = container.resolve("FikaInsuranceService");
      if (
        fikaInsuranceService &&
        typeof fikaInsuranceService.onEndLocalRaidRequest === "function"
      ) {
        console.log(
          "[StatTrackerFinalPatch] FikaInsuranceService instance resolved successfully."
        ); // Używamy console.log
        this.fikaInsuranceServiceInstance = fikaInsuranceService;
        const originalOnEndLocalRaidRequest =
          fikaInsuranceService.onEndLocalRaidRequest;
        console.log(
          "[StatTrackerFinalPatch] Original onEndLocalRaidRequest method stored."
        ); // Używamy console.log

        fikaInsuranceService.onEndLocalRaidRequest = (
          sessionId,
          matchId,
          request
        ) => {
          console.log(
            `[StatTrackerFinalPatch] === FikaInsuranceService.onEndLocalRaidRequest PATCHED! Session: ${sessionId}, MatchId: ${matchId} ===`
          ); // Używamy console.log
          try {
            console.log(
              "[StatTrackerFinalPatch] Calling original FikaInsuranceService.onEndLocalRaidRequest..."
            ); // Używamy console.log
            originalOnEndLocalRaidRequest.call(
              fikaInsuranceService,
              sessionId,
              matchId,
              request
            );
            console.log("[StatTrackerFinalPatch] Original method finished."); // Używamy console.log
          } catch (e) {
            (this.logger || console).error(
              `[StatTrackerPatch] Error calling original onEndLocalRaidRequest: ${e}\n${e.stack}`
            );
          }

          console.log(
            "[StatTrackerFinalPatch] Executing custom raid end processing..."
          ); // Używamy console.log
          try {
            this.saveJsonToDebugFile(
              `onEndLocalRaidRequest_request_${sessionId}_${Date.now()}.json`,
              request
            );

            if (
              !this.currentRaidInfo ||
              this.currentRaidInfo.sessionId !== sessionId
            ) {
              // Używamy logger.warning jeśli dostępny
              (this.logger || console).warn(
                `[StatTrackerFinalPatch] Raid end patch triggered for session ${sessionId}, but no matching start data found.`
              );
              return;
            }

            const exitStatus =
              request?.results?.result?.toLowerCase() ||
              request?.exit?.toLowerCase() ||
              "unknown";
            const exitName =
              request?.exitName || request?.results?.exitName || null;
            const offraidData = request?.results?.profile;

            if (
              offraidData &&
              typeof offraidData === "object" &&
              offraidData.Info &&
              offraidData.Inventory &&
              offraidData.Stats
            ) {
              console.log(
                `[StatTrackerFinalPatch] <<< Found VALID offraidData in patched request! Session: ${sessionId}, Status: ${exitStatus}`
              ); // Używamy console.log
              this.processRaidEndData(
                sessionId,
                exitStatus,
                exitName,
                offraidData
              );
            } else {
              (this.logger || console).error(
                `[StatTrackerFinalPatch] Could not find valid offraidData (request.results.profile) in patched request for session ${sessionId}!`
              );
              this.logObjectDataForDebugging(
                "Invalid/Missing offraidData in request.results",
                offraidData
              );
              this.currentRaidInfo = null;
            }
          } catch (e) {
            (this.logger || console).error(
              `[StatTrackerFinalPatch] Error during custom end processing: ${e}\n${e.stack}`
            );
            this.currentRaidInfo = null;
          }
        };
        console.log(
          "[StatTrackerFinalPatch] FikaInsuranceService.onEndLocalRaidRequest patched successfully!"
        ); // Używamy console.log
      } else {
        (this.logger || console).error(
          "[StatTrackerFinalPatch] FAILED to resolve FikaInsuranceService or its method!"
        );
      }
    } catch (e) {
      (this.logger || console).error(
        `[StatTrackerFinalPatch] CRITICAL Error resolving or patching FikaInsuranceService: ${e}\n${e.stack}`
      );
    }
  }

  // --- Funkcja Pomocnicza do Zapisu JSON ---
  saveJsonToDebugFile(filename, data) {
    // Nadal używamy loggera tutaj, bo jest mniej krytyczne i może być przydatne
    if (!this.jsonUtil) {
      console.error(
        `[StatTrackerFinalPatch] Cannot save debug JSON - jsonUtil missing.`
      );
      return;
    }
    try {
      const debugFolderPath = path.join(__dirname, "debug_logs");
      if (!fs.existsSync(debugFolderPath))
        fs.mkdirSync(debugFolderPath, { recursive: true });
      const filePath = path.join(debugFolderPath, filename);
      const jsonData = this.jsonUtil.serialize(data, true);
      fs.writeFileSync(filePath, jsonData, "utf8");
      // Używamy console.log zamiast logger.log z kolorem
      console.log(`[StatTrackerFinalPatch] Saved debug data to: ${filePath}`);
    } catch (e) {
      (this.logger || console).error(
        `[StatTrackerFinalPatch] Failed to save debug JSON to file ${filename}: ${e}`
      );
      console.log("Raw data that failed to save:");
      console.log(data);
    }
  }

  // --- Funkcja Pomocnicza do Logowania Obiektów ---
  logObjectDataForDebugging(label, data) {
    // Nadal używamy loggera, bo błąd występował przy logowaniu prostych stringów
    if (!this.logger || !this.jsonUtil) {
      console.log(`Cannot log object ${label}, services missing`);
      return;
    }
    try {
      const serializedData = this.jsonUtil.serialize(data, true, 4);
      this.logger.log(
        `[StatTrackerFinalPatch] --- ${label} --- \n${serializedData}`
      );
    } catch (e) {
      // Używamy log bez koloru
      this.logger.error(
        `[StatTrackerFinalPatch] Error serializing data for label "${label}": ${e}`
      );
      console.log(`[StatTrackerFinalPatch] --- ${label} (raw data) --- `);
      console.log(data);
    }
  }

  // --- Pełna Funkcja Przetwarzająca Dane Końca Rajdu ---
  processRaidEndData(sessionId, exitStatus, exitName, offraidData) {
    if (!this.currentRaidInfo || this.currentRaidInfo.sessionId !== sessionId) {
      (this.logger || console).error(
        "[StatTrackerFinalPatch] processRaidEndData called with invalid session or missing currentRaidInfo!"
      );
      this.currentRaidInfo = null;
      return;
    }
    if (!this.databaseServer || !this.jsonUtil) {
      console.error(
        "[StatTrackerFinalPatch] Cannot process raid end data - core services missing!"
      );
      this.currentRaidInfo = null;
      return;
    }
    if (!this.currentRaidInfo) {
      (this.logger || console).warn(
        `[StatTrackerFinalPatch] Attempted to process raid end data for session ${sessionId} again. Skipping.`
      );
      return;
    }

    const raidInfo = this.currentRaidInfo;
    this.currentRaidInfo = null;
    const endTime = Date.now();
    const durationSeconds = Math.floor((endTime - raidInfo.startTime) / 1000);
    const raidResult = exitStatus;
    console.log(
      `[StatTrackerFinalPatch] Processing FULL Raid End Data. Session: ${sessionId}, Status: ${raidResult}, Time: ${durationSeconds}s`
    ); // Używamy console.log

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
        console.log(
          `[StatTrackerFinalPatch] Processed ${processedRaidStats.kills.length} kills for raid ${sessionId}.`
        );
      } // Używamy console.log
      else {
        console.log(
          `[StatTrackerFinalPatch] No victim data in offraidData.Stats for raid ${sessionId}.`
        );
      } // Używamy console.log

      this.updatePersistentStats(processedRaidStats);
      this.savePersistentStats();
    } catch (e) {
      (this.logger || console).error(
        `[StatTrackerFinalPatch] Error during processRaidEndData logic: ${e}\n${e.stack}`
      );
    } finally {
      console.log(
        `[StatTrackerFinalPatch] Finished full raid end processing for session ${sessionId}.`
      );
    } // Używamy console.log
  }

  // --- Standardowe hooki (ignorowane) ---
  onRaidStart(url, info, sessionId, pmcData) {
    /* Ignored */
  }
  onRaidEnd(url, info, sessionId, exitStatus, exitName, offraidData) {
    /* Ignored */
  }

  // --- Metody Pomocnicze (bez zmian) ---
  loadConfig() {
    if (!this.jsonUtil) {
      console.error(
        "[StatTrackerFinalPatch] Cannot load config: JsonUtil not initialized!"
      );
      this.setDefaultConfig();
      return;
    }
    const configPath = path.join(__dirname, "config", "config.json");
    console.log(
      `[StatTrackerFinalPatch] Attempting to load config using 'fs' from: ${configPath}`
    );
    try {
      if (fs.existsSync(configPath)) {
        const configContent = fs.readFileSync(configPath, "utf8");
        this.modConfig = this.jsonUtil.deserialize(configContent);
        console.log(
          "[StatTrackerFinalPatch] Configuration loaded successfully using 'fs'."
        );
        this.ensureDefaultConfigValues();
      } else {
        console.warn(
          `[StatTrackerFinalPatch] Config file not found at ${configPath}. Using default config and attempting to save it.`
        );
        this.setDefaultConfig();
        this.saveConfig();
      }
    } catch (e) {
      console.error(
        `[StatTrackerFinalPatch] Error using 'fs' to load config: ${e}. Using default config.`
      );
      this.setDefaultConfig();
    }
  }
  setDefaultConfig() {
    this.modConfig = {
      enabled: true,
      trackKills: true,
      trackLootValue: false,
      maxRaidHistory: 50,
      persistentStatsFilePath: "stats_data.json",
    };
    console.log("[StatTrackerFinalPatch] Default configuration set/reset.");
  }
  ensureDefaultConfigValues() {
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
    if (changed)
      console.log(
        "[StatTrackerFinalPatch] Added missing default values to loaded config."
      );
  }
  saveConfig() {
    if (!this.jsonUtil) {
      console.error(
        "[StatTrackerFinalPatch] Cannot save config: JsonUtil not initialized!"
      );
      return;
    }
    const configPath = path.join(__dirname, "config", "config.json");
    const configDir = path.join(__dirname, "config");
    try {
      if (!fs.existsSync(configDir)) {
        console.log(
          `[StatTrackerFinalPatch] Creating config directory using 'fs': ${configDir}`
        );
        fs.mkdirSync(configDir, { recursive: true });
      }
      console.log(
        `[StatTrackerFinalPatch] Saving config file using 'fs' to: ${configPath}`
      );
      fs.writeFileSync(
        configPath,
        this.jsonUtil.serialize(this.modConfig, true),
        "utf8"
      );
    } catch (e) {
      console.error(
        `[StatTrackerFinalPatch] Could not save config file using 'fs': ${e}`
      );
    }
  }
  loadPersistentStats() {
    if (!this.jsonUtil) {
      console.error(
        "[StatTrackerFinalPatch] Cannot load persistent stats: JsonUtil not initialized!"
      );
      this.initializePersistentStats();
      return;
    }
    const relativePath =
      this.modConfig.persistentStatsFilePath || "stats_data.json";
    const filePath = path.join(__dirname, relativePath);
    console.log(
      `[StatTrackerFinalPatch] Attempting to load persistent stats using 'fs' from: ${filePath}`
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
          console.warn(
            "[StatTrackerFinalPatch] Loaded persistent stats file seems empty or corrupted. Initializing empty stats."
          );
          this.initializePersistentStats();
        } else {
          console.log(
            "[StatTrackerFinalPatch] Persistent stats loaded successfully using 'fs'."
          );
        }
      } else {
        console.warn(
          `[StatTrackerFinalPatch] Persistent stats file not found at ${filePath}. Initializing empty stats.`
        );
        this.initializePersistentStats();
      }
    } catch (e) {
      console.error(
        `[StatTrackerFinalPatch] Error using 'fs' to load stats: ${e}. Initializing empty stats.`
      );
      this.initializePersistentStats();
    }
  }
  initializePersistentStats() {
    this.persistentStats = {
      totalRaids: 0,
      totalSurvived: 0,
      totalKills: { pmc: 0, scav: 0, boss: 0, other: 0 },
      totalExp: 0,
      averageSurvivalRate: 0,
      raidHistory: [],
      playerStatsSnapshot: {},
    };
    console.log(
      "[StatTrackerFinalPatch] Initialized/reset empty persistent stats object."
    );
  }
  savePersistentStats() {
    if (!this.jsonUtil) {
      console.error(
        "[StatTrackerFinalPatch] Cannot save persistent stats: JsonUtil not initialized!"
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
      console.error(
        `[StatTrackerFinalPatch] Could not save persistent stats file using 'fs': ${e}`
      );
    }
  }
  updatePersistentStats(processedRaidStats) {
    console.log(
      `[StatTrackerFinalPatch] Updating persistent stats with data from raid on ${processedRaidStats.map}.`
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
    this.persistentStats.totalRaids =
      (this.persistentStats.totalRaids || 0) + 1;
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
      (this.persistentStats.totalExp || 0) +
      (processedRaidStats.expGained || 0);
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
    console.log("[StatTrackerFinalPatch] Persistent stats updated.");
  } // Używamy console.log
}

// Rejestracja modu
module.exports = { mod: new DetailedStatsTrackerFikaFinalPatch() };
