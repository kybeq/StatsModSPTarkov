const fs = require("fs");
const path = require("path");
const http = require("http"); // DODANO

const FLASK_API_HOSTNAME = "127.0.0.1"; // DODANO
const FLASK_API_PORT = 5000; // DODANO

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

    this.ensureDebugLogFolderExists();
    this.setDefaultConfig();
    this.initializePersistentStats();
    // notifyFlaskConnected zostanie wywołane w postDBLoad
  }

  async sendToFlask(endpointPath, dataToSend) {
    // Ta funkcja może pozostać async
    const currentLogger = this.logger || {
      info: () => {},
      error: console.error,
    }; // Prosty fallback loggera
    try {
      const serializedData = JSON.stringify(dataToSend);
      const options = {
        hostname: FLASK_API_HOSTNAME,
        port: FLASK_API_PORT,
        path: endpointPath,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(serializedData),
        },
      };

      const req = http.request(options, (res) => {
        let responseData = "";
        res.on("data", (chunk) => (responseData += chunk));
        res.on("end", () => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            // Ograniczone logowanie sukcesu
            // currentLogger.info(`[StatsMods] Flask OK: ${options.path}`);
          } else {
            currentLogger.error(
              `[StatsMods] Flask ERR ${options.path}: ${res.statusCode}`
            );
          }
        });
      });
      req.on("error", (e) => {
        currentLogger.error(
          `[StatsMods] HTTP ERR ${options.path}: ${e.message}`
        );
      });
      req.write(serializedData);
      req.end();
    } catch (e) {
      currentLogger.error(
        `[StatsMods] SendToFlask EXC (${endpointPath}): ${e.message}`
      );
    }
  }

  async notifyFlaskConnected() {
    // Ta funkcja może pozostać async
    const data = { mod: "DetailedStatsTracker", status: "connected_v_min" };
    await this.sendToFlask(`/api/mod/connect`, data);
  }

  ensureDebugLogFolderExists() {
    const debugFolderPath = path.join(__dirname, "debug_logs");
    try {
      if (!fs.existsSync(debugFolderPath)) {
        fs.mkdirSync(debugFolderPath, { recursive: true });
      }
    } catch (e) {
      console.error(`[StatsMods] ERR creating debug_logs: ${e}`);
    }
  }

  preSptLoad(container) {
    try {
      this.logger = container.resolve("WinstonLogger");
    } catch (e) {
      console.error(`[StatsMods] ERR resolving WinstonLogger: ${e}`);
    }
    this.ensureDebugLogFolderExists();
  }

  postDBLoad(container) {
    try {
      this.jsonUtil = container.resolve("JsonUtil");
      this.databaseServer = container.resolve("DatabaseServer");
      this.saveServer = container.resolve("SaveServer");
      this.profileHelper = container.resolve("ProfileHelper");
      // Reszta serwisów...

      this.attemptFikaPatchStart(container);
      this.attemptFikaPatchEnd(container);
      this.loadConfig();
      this.loadPersistentStats();

      this.notifyFlaskConnected().catch((e) =>
        (this.logger || console).error(
          "[StatsMods] NotifyFlask failed in postDBLoad:",
          e.message
        )
      );
      console.log("[StatsMods] Mod initialized.");
    } catch (e) {
      (this.logger || console).error(
        `[StatsMods] CRITICAL postDBLoad ERR: ${e}\n${e.stack}`
      );
    }
  }

  attemptFikaPatchStart(container) {
    try {
      const locationService = container.resolve("LocationLifecycleService");
      if (
        locationService &&
        typeof locationService.startLocalRaid === "function"
      ) {
        const originalStartLocalRaid = locationService.startLocalRaid;
        locationService.startLocalRaid = (sessionId, request) => {
          // USUNIĘTO async
          let originalResult = null;
          try {
            originalResult = originalStartLocalRaid.call(
              locationService,
              sessionId,
              request
            );
          } catch (e) {
            (this.logger || console).error(
              `[StatsMods] ERR calling original startLocalRaid: ${e}\n${e.stack}`
            );
            return originalResult;
          }
          try {
            // this.saveJsonToDebugFile(`startLocalRaid_request_${sessionId}_${Date.now()}.json`, request);
            // this.saveJsonToDebugFile(`startLocalRaid_result_${sessionId}_${Date.now()}.json`, originalResult);
            let pmcData = null;
            if (this.profileHelper) {
              try {
                pmcData =
                  this.profileHelper.getPmcProfile(sessionId) ||
                  this.profileHelper.getFullProfile(sessionId);
              } catch (e) {
                /* cicho */
              }
            }
            const mapName = request?.location?.toLowerCase() || "unknown";
            const timeOfDay =
              request?.timeAndWeatherSettings?.timeVariant ||
              originalResult?.locationLoot?.TimeAndWeatherSettings
                ?.timeVariant ||
              "unknown";
            const weatherSettings =
              request?.timeAndWeatherSettings?.weatherSettings;
            const weather =
              weatherSettings?.cloudiness !== undefined
                ? weatherSettings.cloudiness
                : weatherSettings?.Cloudiness !== undefined
                ? weatherSettings.Cloudiness
                : "unknown";

            if (sessionId && pmcData && this.jsonUtil) {
              try {
                this.currentRaidInfo = {
                  sessionId: sessionId,
                  profileAtStart: this.jsonUtil.clone(pmcData),
                  map: mapName,
                  startTime: Date.now(),
                  timeOfDay: timeOfDay,
                  weather: weather,
                };
              } catch (cloneError) {
                this.currentRaidInfo = null;
              }
            }
            if (pmcData) {
              const flaskStartData = {
                sessionId: sessionId,
                request: {
                  location: request?.location,
                  timeAndWeatherSettings: request?.timeAndWeatherSettings,
                  playerProfile: { Info: pmcData.Info },
                },
              };
              this.sendToFlask(`/api/raid/start`, flaskStartData) // USUNIĘTO await
                .catch((e) =>
                  (this.logger || console).error(
                    `[StatsMods] ERR sending start data (non-blocking): ${e.message}`
                  )
                );
            }
          } catch (e) {
            /* cicho */
          }
          return originalResult;
        };
      } else {
        /* cicho */
      }
    } catch (e) {
      /* cicho */
    }
  }

  attemptFikaPatchEnd(container) {
    let patchedRaidEnd = false;
    try {
      const fikaInsuranceService = container.resolve("FikaInsuranceService");
      if (
        fikaInsuranceService &&
        typeof fikaInsuranceService.onEndLocalRaidRequest === "function"
      ) {
        const originalOnEndLocalRaidRequest =
          fikaInsuranceService.onEndLocalRaidRequest;
        fikaInsuranceService.onEndLocalRaidRequest = (
          sessionId,
          matchId,
          request
        ) => {
          // USUNIĘTO async
          let originalResult;
          try {
            originalResult = originalOnEndLocalRaidRequest.call(
              fikaInsuranceService,
              sessionId,
              matchId,
              request
            );
          } catch (e) {
            (this.logger || console).error(
              `[StatsMods] ERR calling original Fika onEndLocalRaidRequest: ${e}\n${e.stack}`
            );
            return originalResult;
          }
          try {
            // this.saveJsonToDebugFile(`onEndLocalRaidRequest_request_FIKA_${sessionId}_${Date.now()}.json`, request);
            if (request && request.results && request.results.profile) {
              const flaskEndData = { sessionId, matchId, request };
              this.sendToFlask(`/api/raid/end`, flaskEndData) // USUNIĘTO await
                .catch((e) =>
                  (this.logger || console).error(
                    `[StatsMods] ERR sending end data (Fika) (non-blocking): ${e.message}`
                  )
                );
            }
            if (
              !this.currentRaidInfo ||
              this.currentRaidInfo.sessionId !== sessionId
            ) {
              /* cicho */
            } else {
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
                offraidData.Stats &&
                offraidData.Stats.Eft
              ) {
                this.processRaidEndData(
                  sessionId,
                  exitStatus,
                  exitName,
                  offraidData
                ); // USUNIĘTO await
              } else {
                if (
                  this.currentRaidInfo &&
                  this.currentRaidInfo.sessionId === sessionId
                )
                  this.currentRaidInfo = null;
              }
            }
          } catch (e) {
            if (
              this.currentRaidInfo &&
              this.currentRaidInfo.sessionId === sessionId
            )
              this.currentRaidInfo = null;
          }
          return originalResult;
        };
        patchedRaidEnd = true;
      }
    } catch (e) {
      /* cicho */
    }

    if (!patchedRaidEnd) {
      try {
        const inraidController = container.resolve("InraidController");
        if (
          inraidController &&
          typeof inraidController.raidEnd === "function"
        ) {
          const originalRaidEnd = inraidController.raidEnd;
          inraidController.raidEnd = (sessionId, saveProfileRequest) => {
            // USUNIĘTO async
            let originalResult;
            try {
              originalResult = originalRaidEnd.call(
                inraidController,
                sessionId,
                saveProfileRequest
              );
            } catch (e) {
              (this.logger || console).error(
                `[StatsMods] ERR calling original InraidController.raidEnd: ${e}\n${e.stack}`
              );
              return originalResult;
            }
            try {
              // this.saveJsonToDebugFile(`InraidController_raidEnd_request_SPT_${sessionId}_${Date.now()}.json`, saveProfileRequest);
              const offraidData = saveProfileRequest.profile;
              const exitStatus = saveProfileRequest.eftData.exit.toLowerCase();
              const exitName = saveProfileRequest.eftData.exitName;

              if (
                offraidData &&
                typeof offraidData === "object" &&
                offraidData.Info &&
                offraidData.Stats &&
                offraidData.Stats.Eft
              ) {
                const flaskEndData = {
                  sessionId: sessionId,
                  request: {
                    results: {
                      result: exitStatus,
                      exitName: exitName,
                      playTime: saveProfileRequest.eftData.gameTime,
                      profile: offraidData,
                    },
                  },
                };
                this.sendToFlask(`/api/raid/end`, flaskEndData) // USUNIĘTO await
                  .catch((e) =>
                    (this.logger || console).error(
                      `[StatsMods] ERR sending end data (SPT) (non-blocking): ${e.message}`
                    )
                  );

                if (
                  !this.currentRaidInfo ||
                  this.currentRaidInfo.sessionId !== sessionId
                ) {
                  /* cicho */
                } else {
                  this.processRaidEndData(
                    sessionId,
                    exitStatus,
                    exitName,
                    offraidData
                  ); // USUNIĘTO await
                }
              } else {
                if (
                  this.currentRaidInfo &&
                  this.currentRaidInfo.sessionId === sessionId
                )
                  this.currentRaidInfo = null;
              }
            } catch (e) {
              if (
                this.currentRaidInfo &&
                this.currentRaidInfo.sessionId === sessionId
              )
                this.currentRaidInfo = null;
            }
            return originalResult;
          };
        }
      } catch (e) {
        /* cicho */
      }
    }
  }

  saveJsonToDebugFile(filename, data) {
    if (!this.jsonUtil && !JSON.stringify) return;
    try {
      const debugFolderPath = path.join(__dirname, "debug_logs");
      if (!fs.existsSync(debugFolderPath))
        fs.mkdirSync(debugFolderPath, { recursive: true });
      const filePath = path.join(debugFolderPath, filename);
      const jsonData = this.jsonUtil
        ? this.jsonUtil.serialize(data, true)
        : JSON.stringify(data, null, 2);
      fs.writeFileSync(filePath, jsonData, "utf8");
    } catch (e) {
      /* cicho */
    }
  }

  logObjectDataForDebugging(label, data) {
    /* pusta lub minimalne logowanie */
  }

  processRaidEndData(sessionId, exitStatus, exitName, offraidData) {
    // USUNIĘTO async
    if (!this.currentRaidInfo || this.currentRaidInfo.sessionId !== sessionId) {
      this.currentRaidInfo = null;
      return;
    }
    if (!this.databaseServer || !this.jsonUtil) {
      this.currentRaidInfo = null;
      return;
    }
    const raidInfo = this.currentRaidInfo;
    this.currentRaidInfo = null;
    const endTime = Date.now();
    const durationSeconds = Math.floor((endTime - raidInfo.startTime) / 1000);
    const raidResult = exitStatus;
    try {
      let expGainedInRaid = 0;
      if (
        raidInfo.profileAtStart?.Info?.Experience !== undefined &&
        offraidData.Info?.Experience !== undefined
      ) {
        expGainedInRaid =
          offraidData.Info.Experience - raidInfo.profileAtStart.Info.Experience;
      } else {
        expGainedInRaid = offraidData.Info?.Experience || 0;
      }
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
        expGained: expGainedInRaid,
        skillProgress: {},
      };
      if (offraidData.Stats?.Eft?.Victims) {
        const dbItems = this.databaseServer.getTables().templates.items;
        for (const victim of offraidData.Stats.Eft.Victims) {
          let weaponName = "Unknown";
          const weaponIdClean = victim.Weapon?.split(" ")[0];
          if (weaponIdClean && dbItems[weaponIdClean]?._name) {
            weaponName = dbItems[weaponIdClean]._name;
          } else if (victim.Weapon) {
            weaponName = victim.Weapon;
          }
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
      }
      this.updatePersistentStats(processedRaidStats); // USUNIĘTO await
      this.savePersistentStats(); // USUNIĘTO await
    } catch (e) {
      /* cicho */
    }
  }

  onRaidStart(url, info, sessionId, pmcData) {
    /* Ignored */
  }
  onRaidEnd(url, info, sessionId, exitStatus, exitName, offraidData) {
    /* Ignored */
  }

  loadConfig() {
    if (!this.jsonUtil) {
      this.setDefaultConfig();
      return;
    }
    const configPath = path.join(__dirname, "config", "config.json");
    try {
      const configDir = path.dirname(configPath);
      if (!fs.existsSync(configDir))
        fs.mkdirSync(configDir, { recursive: true });
      if (fs.existsSync(configPath)) {
        const configContent = fs.readFileSync(configPath, "utf8");
        this.modConfig = this.jsonUtil.deserialize(configContent);
        this.ensureDefaultConfigValues();
      } else {
        this.setDefaultConfig();
        this.saveConfig();
      }
    } catch (e) {
      this.setDefaultConfig();
    }
  }

  setDefaultConfig() {
    if (typeof this.modConfig !== "object" || this.modConfig === null)
      this.modConfig = {};
    const defaultConfig = {
      enabled: true,
      trackKills: true,
      trackLootValue: false,
      maxRaidHistory: 50,
      persistentStatsFilePath: "stats_data.json",
    };
    this.modConfig = { ...defaultConfig, ...this.modConfig };
    return defaultConfig;
  }

  ensureDefaultConfigValues() {
    const defaultConfig = {
      enabled: true,
      trackKills: true,
      trackLootValue: false,
      maxRaidHistory: 50,
      persistentStatsFilePath: "stats_data.json",
    };
    if (typeof this.modConfig !== "object" || this.modConfig === null)
      this.modConfig = {};
    for (const key in defaultConfig) {
      if (this.modConfig[key] === undefined)
        this.modConfig[key] = defaultConfig[key];
    }
  }

  saveConfig() {
    if (!this.jsonUtil) return;
    const configPath = path.join(__dirname, "config", "config.json");
    const configDir = path.dirname(configPath);
    try {
      if (!fs.existsSync(configDir))
        fs.mkdirSync(configDir, { recursive: true });
      fs.writeFileSync(
        configPath,
        this.jsonUtil.serialize(this.modConfig, true),
        "utf8"
      );
    } catch (e) {
      /* cicho */
    }
  }

  loadPersistentStats() {
    if (!this.jsonUtil) {
      this.initializePersistentStats();
      return;
    }
    const relativePath =
      this.modConfig.persistentStatsFilePath || "stats_data.json";
    const filePath = path.join(__dirname, relativePath);
    try {
      const dirPath = path.dirname(filePath);
      if (!fs.existsSync(dirPath)) fs.mkdirSync(dirPath, { recursive: true });
      if (fs.existsSync(filePath)) {
        const fileContent = fs.readFileSync(filePath, "utf8");
        if (fileContent.trim() === "") {
          this.initializePersistentStats();
        } else {
          this.persistentStats = this.jsonUtil.deserialize(fileContent);
          if (
            typeof this.persistentStats !== "object" ||
            this.persistentStats === null ||
            Object.keys(this.persistentStats).length === 0
          ) {
            this.initializePersistentStats();
          }
        }
      } else {
        this.initializePersistentStats();
      }
    } catch (e) {
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
  }

  savePersistentStats() {
    if (!this.jsonUtil) return;
    const relativePath =
      this.modConfig.persistentStatsFilePath || "stats_data.json";
    const filePath = path.join(__dirname, relativePath);
    try {
      const modDir = path.dirname(filePath);
      if (!fs.existsSync(modDir)) fs.mkdirSync(modDir, { recursive: true });
      fs.writeFileSync(
        filePath,
        this.jsonUtil.serialize(this.persistentStats, true),
        "utf8"
      );
    } catch (e) {
      /* cicho */
    }
  }

  updatePersistentStats(processedRaidStats) {
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
    this.persistentStats.totalSurvived =
      this.persistentStats.totalSurvived || 0;
    this.persistentStats.totalKills.pmc =
      this.persistentStats.totalKills.pmc || 0;
    this.persistentStats.totalKills.scav =
      this.persistentStats.totalKills.scav || 0;
    this.persistentStats.totalKills.boss =
      this.persistentStats.totalKills.boss || 0;
    this.persistentStats.totalKills.other =
      this.persistentStats.totalKills.other || 0;
    this.persistentStats.totalExp =
      (this.persistentStats.totalExp || 0) +
      (processedRaidStats.expGained || 0);

    if (processedRaidStats.status === "survived")
      this.persistentStats.totalSurvived++;
    if (processedRaidStats.kills && Array.isArray(processedRaidStats.kills)) {
      for (const kill of processedRaidStats.kills) {
        const role = kill.role?.toLowerCase() || "other";
        if (role.includes("bear") || role.includes("usec"))
          this.persistentStats.totalKills.pmc++;
        else if (role.includes("savage") || role.includes("playerscav"))
          this.persistentStats.totalKills.scav++;
        else if (role.includes("boss")) this.persistentStats.totalKills.boss++;
        else this.persistentStats.totalKills.other++;
      }
    }
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
  }
}

module.exports = { mod: new DetailedStatsTrackerFikaFinalPatch() };
